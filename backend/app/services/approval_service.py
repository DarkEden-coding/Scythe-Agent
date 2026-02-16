from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.schemas.chat import FileEditOut, ToolCallOut
from app.utils.mappers import map_file_action_for_ui
from app.utils.time import utc_now_iso
from app.utils.auto_approve import matches_auto_approve_rules
from app.utils.json_helpers import safe_parse_json
from app.services.event_bus import EventBus, get_event_bus
from app.tools.registry import ToolRegistry, get_tool_registry


class ApprovalService:
    def __init__(
        self,
        db: Session,
        *,
        event_bus: EventBus | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        self.chat_repo = ChatRepository(db)
        self.settings_repo = SettingsRepository(db)
        self.event_bus = event_bus or get_event_bus()
        self.registry = tool_registry or get_tool_registry()

    def should_auto_approve(self, tool_name: str, input_payload: dict) -> bool:
        rules = self.settings_repo.list_auto_approve_rules()
        return matches_auto_approve_rules(
            tool_name=tool_name, input_payload=input_payload, rules=rules
        )

    async def approve(self, *, chat_id: str, tool_call_id: str) -> tuple[ToolCallOut, list[FileEditOut]]:
        tool_call = self.chat_repo.get_tool_call(tool_call_id)
        if tool_call is None or tool_call.chat_id != chat_id:
            raise ValueError(f"Tool call not found: {tool_call_id}")
        if tool_call.status != "pending":
            raise ValueError(f"Tool call is not pending: {tool_call_id}")

        self.chat_repo.set_tool_call_status(tool_call, status="running")
        self.chat_repo.commit()
        await self.event_bus.publish(
            chat_id,
            {"type": "tool_call_start", "payload": {"toolCall": self._tool_call_out(tool_call).model_dump()}},
        )

        start = datetime.now(timezone.utc)
        file_edits: list[FileEditOut] = []
        try:
            payload = safe_parse_json(tool_call.input_json)
            tool = self.registry.get_tool(tool_call.name)
            if tool is None:
                raise ValueError(f"Tool not registered: {tool_call.name}")
            result = await tool.run(payload)

            for idx, edit in enumerate(result.file_edits):
                row = self.chat_repo.create_file_edit(
                    file_edit_id=f"fe-{tool_call.id}-{idx}",
                    chat_id=chat_id,
                    checkpoint_id=tool_call.checkpoint_id or "",
                    file_path=edit.file_path,
                    action=edit.action,
                    diff=edit.diff,
                    timestamp=utc_now_iso(),
                )
                file_edits.append(
                    FileEditOut(
                        id=row.id,
                        filePath=row.file_path,
                        action=map_file_action_for_ui(row.action),
                        diff=row.diff,
                        timestamp=row.timestamp,
                        checkpointId=row.checkpoint_id,
                    )
                )
                await self.event_bus.publish(
                    chat_id,
                    {"type": "file_edit", "payload": {"fileEdit": file_edits[-1].model_dump()}},
                )

            duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            self.chat_repo.set_tool_call_status(
                tool_call,
                status="completed",
                output_text=result.output,
                duration_ms=duration_ms,
            )
            self.chat_repo.commit()
        except Exception as exc:
            self.chat_repo.set_tool_call_status(tool_call, status="error", output_text=str(exc))
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
        await self.event_bus.publish(
            chat_id,
            {"type": "tool_call_end", "payload": {"toolCall": tool_out.model_dump()}},
        )
        return tool_out, file_edits

    async def reject(self, *, chat_id: str, tool_call_id: str, reason: str | None = None) -> ToolCallOut:
        tool_call = self.chat_repo.get_tool_call(tool_call_id)
        if tool_call is None or tool_call.chat_id != chat_id:
            raise ValueError(f"Tool call not found: {tool_call_id}")
        if tool_call.status != "pending":
            raise ValueError(f"Tool call is not pending: {tool_call_id}")

        message = f"Rejected: {reason}" if reason else "Rejected"
        self.chat_repo.set_tool_call_status(tool_call, status="rejected", output_text=message)
        self.chat_repo.commit()

        tool_out = self._tool_call_out(tool_call)
        await self.event_bus.publish(
            chat_id,
            {"type": "tool_call_end", "payload": {"toolCall": tool_out.model_dump()}},
        )
        return tool_out

    def _tool_call_out(self, tool_call) -> ToolCallOut:
        return ToolCallOut(
            id=tool_call.id,
            name=tool_call.name,
            status=tool_call.status,
            input=safe_parse_json(tool_call.input_json),
            output=tool_call.output_text,
            timestamp=tool_call.timestamp,
            duration=tool_call.duration_ms,
            isParallel=bool(tool_call.parallel) if tool_call.parallel is not None else None,
            parallelGroupId=tool_call.parallel_group,
        )
