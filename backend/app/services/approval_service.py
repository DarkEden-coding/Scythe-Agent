from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.schemas.chat import FileEditOut, TodoOut, ToolCallOut
from app.capabilities.artifacts.store import ArtifactStore
from app.utils.mappers import map_file_action_for_ui
from app.utils.time import utc_now_iso
from app.tools.path_utils import get_tool_outputs_root
from app.utils.auto_approve import matches_auto_approve_rules
from app.utils.json_helpers import safe_parse_json
from app.services.event_bus import EventBus, get_event_bus
from app.tools.registry import ToolRegistry, get_tool_registry
from app.utils.ids import generate_id


class _ToolRunKwargs(TypedDict, total=False):
    project_root: str | None
    chat_id: str
    chat_repo: ChatRepository | None
    checkpoint_id: str | None
    tool_call_id: str


class ApprovalService:
    def __init__(
        self,
        db: Session,
        *,
        event_bus: EventBus | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        self.chat_repo = ChatRepository(db)
        self.project_repo = ProjectRepository(db)
        self.settings_repo = SettingsRepository(db)
        self.event_bus = event_bus or get_event_bus()
        self.registry = tool_registry or get_tool_registry()
        self.artifact_store = ArtifactStore()

    def should_auto_approve(self, tool_name: str, input_payload: dict) -> bool:
        entry = next((e for e in self.registry.list_entries() if e.name == tool_name), None)
        if entry and entry.approval_policy == "always":
            return True
        if entry and entry.approval_policy == "manual":
            return False
        if tool_name == "read_file":
            path_val = str(input_payload.get("path", ""))
            if path_val:
                try:
                    target = Path(path_val).expanduser().resolve()
                    target.relative_to(get_tool_outputs_root())
                    return True
                except (ValueError, OSError):
                    pass
        rules = self.settings_repo.list_auto_approve_rules()
        return matches_auto_approve_rules(
            tool_name=tool_name, input_payload=input_payload, rules=rules
        )

    async def approve(
        self, *, chat_id: str, tool_call_id: str
    ) -> tuple[ToolCallOut, list[FileEditOut]]:
        tool_call = self.chat_repo.get_tool_call(tool_call_id)
        if tool_call is None or tool_call.chat_id != chat_id:
            raise ValueError(f"Tool call not found: {tool_call_id}")
        if tool_call.status != "pending":
            raise ValueError(f"Tool call is not pending: {tool_call_id}")

        self.chat_repo.set_tool_call_status(tool_call, status="running")
        self.chat_repo.commit()
        tc_payload = self._tool_call_out(tool_call).model_dump()
        if tool_call.checkpoint_id:
            tc_payload["checkpointId"] = tool_call.checkpoint_id
        await self.event_bus.publish(
            chat_id,
            {"type": "tool_call_start", "payload": {"toolCall": tc_payload}},
        )

        start = datetime.now(timezone.utc)
        file_edits: list[FileEditOut] = []
        try:
            payload = safe_parse_json(tool_call.input_json)
            tool = self.registry.get_tool(tool_call.name)
            if tool is None:
                raise ValueError(f"Tool not registered: {tool_call.name}")
            project_root = None
            chat = self.chat_repo.get_chat(chat_id)
            if chat:
                project = self.project_repo.get_project(chat.project_id)
                if project and project.path:
                    project_root = project.path
            run_kwargs: _ToolRunKwargs = {
                "project_root": project_root,
                "chat_id": chat_id,
                "chat_repo": self.chat_repo,
                "tool_call_id": tool_call.id,
            }
            checkpoint_id = tool_call.checkpoint_id
            if tool_call.name == "update_todo_list" and checkpoint_id is not None:
                run_kwargs["checkpoint_id"] = checkpoint_id
            result = await tool.run(payload, **run_kwargs)

            output_to_store = result.output
            created_artifacts: list[dict] = []
            if chat:
                mem = self.settings_repo.get_memory_settings()
                preview, artifacts = self.artifact_store.materialize_tool_output(
                    result.output,
                    project_id=chat.project_id,
                    max_tokens=mem.get("tool_output_token_threshold"),
                    preview_tokens=mem.get("tool_output_preview_tokens"),
                )
                output_to_store = preview
                for artifact in artifacts:
                    self.chat_repo.create_tool_artifact(
                        artifact_id=generate_id("ta"),
                        tool_call_id=tool_call.id,
                        chat_id=chat_id,
                        project_id=chat.project_id,
                        artifact_type=artifact.artifact_type,
                        file_path=artifact.file_path,
                        line_count=artifact.total_tokens,
                        preview_lines=artifact.preview_tokens,
                        created_at=utc_now_iso(),
                    )
                    created_artifacts.append(
                        {
                            "type": artifact.artifact_type,
                            "path": artifact.file_path,
                            "lineCount": artifact.total_tokens,
                            "previewLines": artifact.preview_tokens,
                        }
                    )

            for idx, edit in enumerate(result.file_edits):
                edit_ts = utc_now_iso()
                file_edit_id = f"fe-{tool_call.id}-{idx}"
                row = self.chat_repo.create_file_edit(
                    file_edit_id=file_edit_id,
                    chat_id=chat_id,
                    checkpoint_id=tool_call.checkpoint_id or "",
                    file_path=edit.file_path,
                    action=edit.action,
                    diff=edit.diff,
                    timestamp=edit_ts,
                )
                self.chat_repo.create_file_snapshot(
                    snapshot_id=generate_id("snap"),
                    chat_id=chat_id,
                    checkpoint_id=tool_call.checkpoint_id or None,
                    file_edit_id=file_edit_id,
                    file_path=edit.file_path,
                    content=edit.original_content,
                    timestamp=edit_ts,
                )
                file_checkpoint_id = row.checkpoint_id or ""
                file_edits.append(
                    FileEditOut(
                        id=row.id,
                        filePath=row.file_path,
                        action=map_file_action_for_ui(row.action),
                        diff=row.diff,
                        timestamp=row.timestamp,
                        checkpointId=file_checkpoint_id,
                    )
                )
                await self.event_bus.publish(
                    chat_id,
                    {
                        "type": "file_edit",
                        "payload": {"fileEdit": file_edits[-1].model_dump()},
                    },
                )

            duration_ms = int(
                (datetime.now(timezone.utc) - start).total_seconds() * 1000
            )
            self.chat_repo.set_tool_call_status(
                tool_call,
                status="error" if not result.ok else "completed",
                output_text=output_to_store,
                duration_ms=duration_ms,
            )
            self.chat_repo.commit()

            if tool_call.name == "update_todo_list" and result.ok:
                todos = self.chat_repo.get_current_todos(chat_id)
                todos_out = [
                    TodoOut(
                        id=t["id"],
                        content=t["content"],
                        status=t["status"],
                        sortOrder=t["sort_order"],
                        timestamp=t["timestamp"],
                    )
                    for t in todos
                ]
                await self.event_bus.publish(
                    chat_id,
                    {
                        "type": "todo_list_updated",
                        "payload": {"todos": [o.model_dump() for o in todos_out]},
                    },
                )
        except Exception as exc:
            duration_ms = int(
                (datetime.now(timezone.utc) - start).total_seconds() * 1000
            )
            self.chat_repo.set_tool_call_status(
                tool_call,
                status="error",
                output_text=str(exc),
                duration_ms=duration_ms,
            )
            self.chat_repo.commit()
            await self.event_bus.publish(
                chat_id,
                {
                    "type": "error",
                    "payload": {
                        "toolCallId": tool_call.id,
                        "toolName": tool_call.name,
                        "message": str(exc),
                    },
                },
            )

        tool_out = self._tool_call_out(tool_call)
        tc_payload = tool_out.model_dump()
        if tool_call.checkpoint_id:
            tc_payload["checkpointId"] = tool_call.checkpoint_id
        await self.event_bus.publish(
            chat_id,
            {"type": "tool_call_end", "payload": {"toolCall": tc_payload}},
        )
        return tool_out, file_edits

    async def reject(
        self, *, chat_id: str, tool_call_id: str, reason: str | None = None
    ) -> ToolCallOut:
        tool_call = self.chat_repo.get_tool_call(tool_call_id)
        if tool_call is None or tool_call.chat_id != chat_id:
            raise ValueError(f"Tool call not found: {tool_call_id}")
        if tool_call.status != "pending":
            raise ValueError(f"Tool call is not pending: {tool_call_id}")

        message = f"Rejected: {reason}" if reason else "Rejected"
        self.chat_repo.set_tool_call_status(
            tool_call, status="rejected", output_text=message
        )
        self.chat_repo.commit()

        tool_out = self._tool_call_out(tool_call)
        tc_payload = tool_out.model_dump()
        if tool_call.checkpoint_id:
            tc_payload["checkpointId"] = tool_call.checkpoint_id
        await self.event_bus.publish(
            chat_id,
            {"type": "tool_call_end", "payload": {"toolCall": tc_payload}},
        )
        return tool_out

    def _tool_call_out(self, tool_call) -> ToolCallOut:
        artifacts = []
        for artifact in self.chat_repo.list_tool_artifacts_for_tool_call(tool_call.id):
            artifacts.append(
                {
                    "type": artifact.artifact_type,
                    "path": artifact.file_path,
                    "lineCount": artifact.line_count,
                    "previewLines": artifact.preview_lines,
                }
            )
        return ToolCallOut(
            id=tool_call.id,
            name=tool_call.name,
            status=tool_call.status,
            input=safe_parse_json(tool_call.input_json),
            output=tool_call.output_text,
            timestamp=tool_call.timestamp,
            duration=tool_call.duration_ms,
            isParallel=bool(tool_call.parallel)
            if tool_call.parallel is not None
            else None,
            parallelGroupId=tool_call.parallel_group,
            artifacts=artifacts,
        )
