import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Mapping, cast

import httpx
from sqlalchemy.orm import Session

from app.db.models.chat import Chat
from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.db.session import get_sessionmaker
from app.initial_information import apply_initial_information
from app.schemas.chat import (
    ApprovePlanResponse,
    ContinueAgentResponse,
    CheckpointOut,
    EditMessageResponse,
    GetChatHistoryResponse,
    MessageOut,
    ProjectPlanOut,
    SendMessageResponse,
    UpdatePlanResponse,
)
from app.services.approval_service import ApprovalService
from app.services.agent_task_manager import AgentTaskManager, get_agent_task_manager
from app.services.chat_history import ChatHistoryAssembler
from app.services.event_bus import EventBus, get_event_bus
from app.services.memory.observational.background import get_om_background_runner
from app.services.revert_service import RevertService
from app.services.runtime_orchestrator import run_agent_turn
from app.services.plan_service import PlanService
from app.services.settings_service import SettingsService
from app.tools.path_utils import resolve_path
from app.utils.ids import generate_id
from app.utils.json_helpers import safe_parse_json
from app.utils.mappers import map_role_for_ui
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)
_MENTION_PATTERN = re.compile(r"(?<![A-Za-z0-9_.-])@([^\s@]+)")
_TRAILING_MENTION_PUNCTUATION = ".,;:!?)]}>\"'"
_MAX_MENTION_FILES_PER_MESSAGE = 8
_MENTION_INPUT_FLAG = "__mention_reference__"

# Matches {{FILE:i}} plus any trailing stray braces for scrubbing labels/previews
_LABEL_PLACEHOLDER_PATTERN = re.compile(r"\{\{FILE:(\d+)\}\}\}*")


def _scrub_content_for_label(content: str, reference_paths: list[str]) -> str:
    """Replace {{FILE:i}} placeholders (and stray trailing braces) with filenames."""

    def repl(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        if 0 <= idx < len(reference_paths):
            return Path(reference_paths[idx]).name
        return ""

    return _LABEL_PLACEHOLDER_PATTERN.sub(repl, content)


def _extract_http_error_detail(body: object) -> str:
    """Best-effort extraction of a useful provider error message from JSON/text bodies."""
    if isinstance(body, Mapping):
        body_dict = cast(dict[str, object], body)
        err = body_dict.get("error")
        if isinstance(err, dict):
            err_dict = cast(dict[str, object], err)
            msg = err_dict.get("message")
            typ = err_dict.get("type")
            param = err_dict.get("param")
            parts = [str(msg).strip()] if isinstance(msg, str) and str(msg).strip() else []
            if isinstance(typ, str) and typ.strip():
                parts.append(f"type={typ.strip()}")
            if isinstance(param, str) and param.strip():
                parts.append(f"param={param.strip()}")
            if parts:
                return " | ".join(parts)
        msg = body_dict.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()
        detail = body_dict.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if isinstance(detail, list):
            joined = ", ".join(str(x).strip() for x in detail if str(x).strip())
            if joined:
                return joined
        try:
            compact = json.dumps(body_dict, separators=(",", ":"), ensure_ascii=True)
            return compact[:500]
        except Exception:
            return ""
    if isinstance(body, str):
        text = body.strip()
        if text:
            return text[:500]
    return ""


def _format_runtime_error(exc: Exception) -> str:
    """Create a user-facing runtime error with upstream details when available."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        url = str(exc.request.url)
        detail = ""
        try:
            detail = _extract_http_error_detail(exc.response.json())
        except Exception:
            try:
                detail = _extract_http_error_detail(exc.response.text)
            except Exception:
                detail = ""

        base = f"Upstream request failed ({status}) for {url}."
        return f"{base} {detail}".strip() if detail else base

    msg = str(exc).strip()
    return msg or f"{exc.__class__.__name__} (no details)"


class ChatService:
    def __init__(
        self,
        db: Session,
        event_bus: EventBus | None = None,
        task_manager: AgentTaskManager | None = None,
    ):
        self.repo = ChatRepository(db)
        self.settings_repo = SettingsRepository(db)
        self.settings_service = SettingsService(db)
        self.event_bus = event_bus or get_event_bus()
        self.task_manager = task_manager or get_agent_task_manager()

    def _persist_user_turn(
        self,
        *,
        chat: Chat,
        content: str,
        checkpoint_label: str,
    ) -> tuple[MessageOut, CheckpointOut]:
        timestamp = utc_now_iso()
        message = self.repo.create_message(
            message_id=generate_id("msg"),
            chat_id=chat.id,
            role="user",
            content=content,
            timestamp=timestamp,
            checkpoint_id=None,
        )
        checkpoint = self.repo.create_checkpoint(
            checkpoint_id=generate_id("cp"),
            chat_id=chat.id,
            message_id=message.id,
            label=checkpoint_label,
            timestamp=timestamp,
        )
        self.repo.link_message_checkpoint(message, checkpoint.id)
        self.repo.update_chat_timestamp(chat, timestamp)
        self.repo.commit()

        message_out = MessageOut(
            id=message.id,
            role=map_role_for_ui(message.role),
            content=message.content,
            timestamp=message.timestamp,
            checkpointId=checkpoint.id,
            referencedFiles=[],
        )
        checkpoint_out = CheckpointOut(
            id=checkpoint.id,
            messageId=checkpoint.message_id,
            timestamp=checkpoint.timestamp,
            label=checkpoint.label,
            fileEdits=[],
            toolCalls=[],
            reasoningBlocks=[],
        )
        return message_out, checkpoint_out

    def _extract_mention_tokens(self, content: str) -> list[str]:
        if "@" not in content:
            return []
        tokens: list[str] = []
        seen = set()
        for match in _MENTION_PATTERN.finditer(content):
            raw = match.group(1).strip()
            token = raw.rstrip(_TRAILING_MENTION_PUNCTUATION).strip()
            if not token:
                continue
            if token in seen:
                continue
            seen.add(token)
            tokens.append(token)
            if len(tokens) >= _MAX_MENTION_FILES_PER_MESSAGE:
                break
        return tokens

    def _resolve_mention_paths(
        self,
        *,
        content: str,
        project_root: str | None,
    ) -> list[str]:
        if not project_root:
            return []
        root = Path(project_root).expanduser().resolve()
        resolved_paths: list[str] = []
        seen = set()
        for token in self._extract_mention_tokens(content):
            candidate = Path(token)
            absolute_candidate = candidate if candidate.is_absolute() else (root / candidate)
            try:
                resolved = resolve_path(str(absolute_candidate), project_root=str(root), allow_external=False)
            except ValueError:
                continue
            if not resolved.exists() or not resolved.is_file():
                continue
            resolved_str = str(resolved)
            if resolved_str in seen:
                continue
            seen.add(resolved_str)
            resolved_paths.append(resolved_str)
        return resolved_paths

    def _resolve_explicit_reference_paths(
        self,
        *,
        referenced_files: list[str] | None,
        project_root: str | None,
    ) -> list[str]:
        if not project_root or not referenced_files:
            return []
        root = Path(project_root).expanduser().resolve()
        resolved_paths: list[str] = []
        seen = set()
        for raw_path in referenced_files:
            candidate_text = str(raw_path or "").strip()
            if not candidate_text:
                continue
            candidate = Path(candidate_text)
            absolute_candidate = candidate if candidate.is_absolute() else (root / candidate)
            try:
                resolved = resolve_path(
                    str(absolute_candidate),
                    project_root=str(root),
                    allow_external=False,
                )
            except ValueError:
                continue
            if not resolved.exists() or not resolved.is_file():
                continue
            resolved_str = str(resolved)
            if resolved_str in seen:
                continue
            seen.add(resolved_str)
            resolved_paths.append(resolved_str)
        return resolved_paths

    def _collect_reference_paths(
        self,
        *,
        content: str,
        referenced_files: list[str] | None,
        project_root: str | None,
    ) -> list[str]:
        combined: list[str] = []
        seen = set()
        for path in self._resolve_explicit_reference_paths(
            referenced_files=referenced_files,
            project_root=project_root,
        ):
            if path in seen:
                continue
            seen.add(path)
            combined.append(path)
        for path in self._resolve_mention_paths(content=content, project_root=project_root):
            if path in seen:
                continue
            seen.add(path)
            combined.append(path)
        return combined

    def _extract_mentioned_tool_calls_by_checkpoint(
        self,
        tool_calls: list,
    ) -> dict[str, list[tuple[object, str]]]:
        by_checkpoint: dict[str, list[tuple[object, str]]] = {}
        for tc in tool_calls:
            if not tc.checkpoint_id or tc.name != "read_file":
                continue
            payload = safe_parse_json(tc.input_json)
            if not bool(payload.get(_MENTION_INPUT_FLAG)):
                continue
            path = str(payload.get("path", "")).strip()
            if not path:
                continue
            by_checkpoint.setdefault(tc.checkpoint_id, []).append((tc, path))
        return by_checkpoint

    def _build_mention_injected_messages(
        self,
        mentioned_tool_calls: list[tuple[object, str]],
    ) -> list[dict]:
        injected_messages: list[dict] = []
        for tc, path in mentioned_tool_calls:
            if getattr(tc, "status", None) == "pending":
                continue
            tool_call_id = str(getattr(tc, "id", "")).strip()
            if not tool_call_id:
                continue
            model_args_json = json.dumps({"path": path}, separators=(",", ":"))
            injected_messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": model_args_json,
                            },
                        }
                    ],
                    "_message_id": generate_id("msg"),
                }
            )
            injected_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": str(getattr(tc, "output_text", "") or ""),
                    "_message_id": generate_id("msg"),
                }
            )
        return injected_messages

    async def _hydrate_file_mentions(
        self,
        *,
        chat_id: str,
        checkpoint_id: str,
        file_paths: list[str],
    ) -> tuple[list[str], list[dict]]:
        if not file_paths:
            return ([], [])

        approval_service = ApprovalService(self.repo.db, event_bus=self.event_bus)
        tool_call_ids: list[str] = []
        injected_messages: list[dict] = []
        for file_path in file_paths:
            tool_call_id = generate_id("tc")
            input_payload = {"path": file_path, _MENTION_INPUT_FLAG: True}
            input_json = json.dumps(input_payload, separators=(",", ":"))
            model_args_json = json.dumps({"path": file_path}, separators=(",", ":"))
            self.repo.create_tool_call(
                tool_call_id=tool_call_id,
                chat_id=chat_id,
                checkpoint_id=checkpoint_id,
                name="read_file",
                status="pending",
                input_json=input_json,
                timestamp=utc_now_iso(),
                parallel_group=None,
            )
            self.repo.commit()

            try:
                tool_call_out, _ = await approval_service.approve(
                    chat_id=chat_id,
                    tool_call_id=tool_call_id,
                )
            except Exception:
                logger.warning(
                    "Failed to pre-read mentioned file for chat_id=%s path=%s",
                    chat_id,
                    file_path,
                    exc_info=True,
                )
                continue

            tool_call_ids.append(tool_call_id)
            injected_messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": model_args_json,
                            },
                        }
                    ],
                    "_message_id": generate_id("msg"),
                }
            )
            injected_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": tool_call_out.output or "",
                    "_message_id": generate_id("msg"),
                }
            )
        return (tool_call_ids, injected_messages)

    async def _deny_pending_and_cancel_agent(
        self, chat_id: str, reject_reason: str = "User sent new message"
    ) -> bool:
        """Deny any pending tool approvals and cancel the running agent for this chat.
        Returns True if a task was cancelled."""
        # Cancel any in-flight observation cycle for this chat.
        get_om_background_runner().cancel(chat_id)

        cancelled_task = False
        existing_task = self.task_manager.pop(chat_id)
        if existing_task is not None and not existing_task.done():
            for tc in self.repo.list_tool_calls(chat_id):
                if tc.status == "pending":
                    try:
                        await ApprovalService(self.repo.db).reject(
                            chat_id=chat_id,
                            tool_call_id=tc.id,
                            reason=reject_reason,
                        )
                    except ValueError:
                        pass
            existing_task.cancel()
            try:
                await existing_task
            except (asyncio.CancelledError, Exception):
                pass
            cancelled_task = True

        await self._cancel_running_sub_agents(chat_id)
        return cancelled_task

    async def _cancel_running_sub_agents(self, chat_id: str) -> None:
        """Mark any lingering in-progress sub-agent runs as cancelled and publish end events."""
        changed = []
        for run in self.repo.list_sub_agent_runs(chat_id):
            if run.status not in {"pending", "running"}:
                continue
            output_text = run.output_text or "Sub-agent cancelled."
            self.repo.set_sub_agent_run_status(
                run,
                status="cancelled",
                output_text=output_text,
            )
            changed.append((run.id, run.tool_call_id, output_text, run.duration_ms))

        if not changed:
            return
        self.repo.commit()

        for sub_agent_id, tool_call_id, output_text, duration_ms in changed:
            await self.event_bus.publish(
                chat_id,
                {
                    "type": "sub_agent_end",
                    "payload": {
                        "subAgentId": sub_agent_id,
                        "toolCallId": tool_call_id,
                        "status": "cancelled",
                        "output": output_text,
                        "duration": duration_ms or 0,
                    },
                },
            )

    async def cancel_agent(self, chat_id: str) -> bool:
        """Cancel the running agent for this chat. Returns True if a task was cancelled."""
        return await self._deny_pending_and_cancel_agent(chat_id, "User cancelled")

    async def continue_agent(self, chat_id: str) -> ContinueAgentResponse:
        """Resume agent execution for an existing chat/checkpoint without creating a new user message."""
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        await self._deny_pending_and_cancel_agent(chat_id, "User requested continue")

        checkpoints = self.repo.list_checkpoints(chat_id)
        if not checkpoints:
            raise ValueError(f"No checkpoint found for chat: {chat_id}")
        checkpoint = checkpoints[-1]

        source_message = self.repo.get_message(checkpoint.message_id)
        content = source_message.content if source_message is not None else ""
        mentioned_by_checkpoint = self._extract_mentioned_tool_calls_by_checkpoint(
            self.repo.list_tool_calls(chat_id)
        )
        mention_messages = self._build_mention_injected_messages(
            mentioned_by_checkpoint.get(checkpoint.id, [])
        )

        _schedule_background_task(
            chat_id=chat_id,
            checkpoint_id=checkpoint.id,
            content=content,
            mode="default",
            active_plan_id=None,
            extra_messages=mention_messages,
            session_factory=get_sessionmaker(),
            event_bus=self.event_bus,
            task_manager=self.task_manager,
        )
        return ContinueAgentResponse(started=True, checkpointId=checkpoint.id)

    async def send_message(
        self,
        chat_id: str,
        content: str,
        *,
        mode: str = "default",
        active_plan_id: str | None = None,
        referenced_files: list[str] | None = None,
    ) -> SendMessageResponse:
        mode_name = mode if mode in {"default", "planning", "plan_edit"} else "default"
        if mode_name == "plan_edit" and not active_plan_id:
            raise ValueError("activePlanId is required for plan_edit mode")
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        if mode_name == "plan_edit":
            plan = self.repo.get_project_plan(active_plan_id or "")
            if plan is None or plan.chat_id != chat_id:
                raise ValueError(f"Plan not found: {active_plan_id}")

        await self._deny_pending_and_cancel_agent(chat_id)

        existing_messages = self.repo.list_messages(chat_id)
        is_first_message = len(existing_messages) == 0
        if is_first_message and chat.title == "New chat":
            title = content.strip()[:64] or "New chat"
            chat.title = title

        project = ProjectRepository(self.repo.db).get_project(chat.project_id)
        reference_paths = self._collect_reference_paths(
            content=content,
            referenced_files=referenced_files,
            project_root=project.path if project else None,
        )
        label_content = _scrub_content_for_label(content, reference_paths)[:48]

        timestamp = utc_now_iso()
        message = self.repo.create_message(
            message_id=generate_id("msg"),
            chat_id=chat_id,
            role="user",
            content=content,
            timestamp=timestamp,
            checkpoint_id=None,
        )
        checkpoint = self.repo.create_checkpoint(
            checkpoint_id=generate_id("cp"),
            chat_id=chat_id,
            message_id=message.id,
            label=f"User message: {label_content}",
            timestamp=timestamp,
        )
        self.repo.link_message_checkpoint(message, checkpoint.id)
        self.repo.update_chat_timestamp(chat, timestamp)
        self.repo.commit()

        message_out = MessageOut(
            id=message.id,
            role=map_role_for_ui(message.role),
            content=message.content,
            timestamp=message.timestamp,
            checkpointId=checkpoint.id,
            referencedFiles=[],
        )
        checkpoint_out = CheckpointOut(
            id=checkpoint.id,
            messageId=checkpoint.message_id,
            timestamp=checkpoint.timestamp,
            label=checkpoint.label,
            fileEdits=[],
            toolCalls=[],
            reasoningBlocks=[],
        )
        mention_tool_call_ids, mention_messages = await self._hydrate_file_mentions(
            chat_id=chat_id,
            checkpoint_id=checkpoint.id,
            file_paths=reference_paths,
        )
        message_out.referencedFiles = reference_paths
        checkpoint_out.toolCalls = mention_tool_call_ids

        if is_first_message and chat.title != "New chat":
            await self.event_bus.publish(
                chat_id,
                {
                    "type": "chat_title_updated",
                    "payload": {"chatId": chat_id, "title": chat.title},
                },
            )
        await self.event_bus.publish(
            chat_id,
            {"type": "message", "payload": {"message": message_out.model_dump()}},
        )
        await self.event_bus.publish(
            chat_id,
            {
                "type": "checkpoint",
                "payload": {"checkpoint": checkpoint_out.model_dump()},
            },
        )

        _schedule_background_task(
            chat_id=chat_id,
            checkpoint_id=checkpoint.id,
            content=content,
            mode=mode_name,
            active_plan_id=active_plan_id,
            extra_messages=mention_messages,
            session_factory=get_sessionmaker(),
            event_bus=self.event_bus,
            task_manager=self.task_manager,
        )
        return SendMessageResponse(message=message_out, checkpoint=checkpoint_out)

    async def edit_message(
        self,
        chat_id: str,
        message_id: str,
        content: str,
        referenced_files: list[str] | None = None,
    ) -> EditMessageResponse:
        message = self.repo.get_message(message_id)
        if message is None or message.chat_id != chat_id:
            raise ValueError(f"Message not found: {message_id}")
        if message.role != "user":
            raise ValueError("Only user messages can be edited")

        checkpoint = self.repo.get_checkpoint_by_message(message_id)
        if checkpoint is None:
            raise ValueError(f"No checkpoint found for message: {message_id}")

        # Prevent stale observation writes while we mutate/revert history.
        get_om_background_runner().cancel(chat_id)

        # Cancel any running agent task for this chat
        existing_task = self.task_manager.pop(chat_id)
        if existing_task is not None and not existing_task.done():
            existing_task.cancel()
            try:
                await existing_task
            except (asyncio.CancelledError, Exception):
                pass

        # Revert filesystem + DB to this checkpoint
        revert_svc = RevertService(self.repo.db)
        reverted = revert_svc.revert_to_checkpoint(chat_id, checkpoint.id)

        chat_row = self.repo.get_chat(chat_id)
        project_path = None
        if chat_row is not None:
            project = ProjectRepository(self.repo.db).get_project(chat_row.project_id)
            if project is not None:
                project_path = project.path
        reference_paths = self._collect_reference_paths(
            content=content,
            referenced_files=referenced_files,
            project_root=project_path,
        )

        # Update message content and checkpoint label in-place
        message = self.repo.get_message(message_id)
        if message is not None:
            message.content = content
        cp = self.repo.get_checkpoint(checkpoint.id)
        if cp is not None:
            label_content = _scrub_content_for_label(content, reference_paths)[:48]
            cp.label = f"User message: {label_content}"
        self.repo.commit()

        # Publish message_edited event so frontend can update state
        await self.event_bus.publish(
            chat_id,
            {
                "type": "message_edited",
                "payload": {
                    "revertedHistory": reverted.model_dump(),
                    "messageId": message_id,
                    "content": content,
                    "referencedFiles": reference_paths,
                },
            },
        )

        _, mention_messages = await self._hydrate_file_mentions(
            chat_id=chat_id,
            checkpoint_id=checkpoint.id,
            file_paths=reference_paths,
        )

        _schedule_background_task(
            chat_id=chat_id,
            checkpoint_id=checkpoint.id,
            content=content,
            mode="default",
            active_plan_id=None,
            extra_messages=mention_messages,
            session_factory=get_sessionmaker(),
            event_bus=self.event_bus,
            task_manager=self.task_manager,
        )
        return EditMessageResponse(revertedHistory=reverted)

    async def list_plans(self, chat_id: str) -> list[ProjectPlanOut]:
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")
        plan_svc = PlanService(self.repo.db, event_bus=self.event_bus)
        for row in self.repo.list_project_plans(chat_id):
            await plan_svc.sync_external_if_needed(chat_id, row.id)
        return await plan_svc.list_plans(chat_id, include_content=True)

    async def get_plan(self, chat_id: str, plan_id: str) -> ProjectPlanOut:
        plan_svc = PlanService(self.repo.db, event_bus=self.event_bus)
        await plan_svc.sync_external_if_needed(chat_id, plan_id)
        return await plan_svc.get_plan(chat_id, plan_id, include_content=True)

    async def update_plan(
        self,
        chat_id: str,
        plan_id: str,
        *,
        content: str,
        title: str | None = None,
        base_revision: int | None = None,
        last_editor: str = "user",
    ) -> UpdatePlanResponse:
        plan_svc = PlanService(self.repo.db, event_bus=self.event_bus)
        result = await plan_svc.update_plan(
            chat_id=chat_id,
            plan_id=plan_id,
            content=content,
            title=title,
            base_revision=base_revision,
            last_editor=last_editor,
        )
        return UpdatePlanResponse(plan=result.plan, conflict=result.conflict)

    async def approve_plan(
        self,
        chat_id: str,
        plan_id: str,
        *,
        action: str,
    ) -> ApprovePlanResponse:
        if action not in {"keep_context", "clear_context"}:
            raise ValueError("action must be keep_context or clear_context")

        plan_svc = PlanService(self.repo.db, event_bus=self.event_bus)
        await plan_svc.sync_external_if_needed(chat_id, plan_id)
        plan = await plan_svc.get_plan(chat_id, plan_id, include_content=True)
        markdown = (plan.content or "").strip()
        kickoff_content = (
            f"Implement approved plan {plan_id}. Plan file: {plan.filePath}\n\n{markdown}"
            if markdown
            else f"Implement approved plan {plan_id}. Plan file: {plan.filePath}"
        )

        if action == "keep_context":
            chat = self.repo.get_chat(chat_id)
            if chat is None:
                raise ValueError(f"Chat not found: {chat_id}")
            message_out, checkpoint_out = self._persist_user_turn(
                chat=chat,
                content=kickoff_content,
                checkpoint_label=f"Implement approved plan: {plan.title[:40]}",
            )
            await self.event_bus.publish(
                chat_id,
                {"type": "message", "payload": {"message": message_out.model_dump()}},
            )
            await self.event_bus.publish(
                chat_id,
                {"type": "checkpoint", "payload": {"checkpoint": checkpoint_out.model_dump()}},
            )
            updated = await plan_svc.mark_plan_status(
                chat_id=chat_id,
                plan_id=plan_id,
                status="implementing",
                approved_action=action,
                implementation_chat_id=chat_id,
            )
            _schedule_background_task(
                chat_id=chat_id,
                checkpoint_id=checkpoint_out.id,
                content=kickoff_content,
                mode="default",
                active_plan_id=None,
                session_factory=get_sessionmaker(),
                event_bus=self.event_bus,
                task_manager=self.task_manager,
            )
            return ApprovePlanResponse(plan=updated, implementationChatId=chat_id)

        project_repo = ProjectRepository(self.repo.db)
        source_chat = self.repo.get_chat(chat_id)
        if source_chat is None:
            raise ValueError(f"Chat not found: {chat_id}")
        project = project_repo.get_project(source_chat.project_id)
        if project is None:
            raise ValueError(f"Project not found: {source_chat.project_id}")

        now = utc_now_iso()
        implementation_chat_id = generate_id("chat")
        new_chat = Chat(
            id=implementation_chat_id,
            project_id=source_chat.project_id,
            title=f"Implement: {plan.title[:48]}",
            created_at=now,
            updated_at=now,
            sort_order=project_repo.get_next_chat_sort_order(source_chat.project_id),
            is_pinned=0,
        )
        project_repo.create_chat(new_chat)
        project.last_active = now
        self.repo.commit()

        message_out, checkpoint_out = self._persist_user_turn(
            chat=new_chat,
            content=kickoff_content,
            checkpoint_label=f"Implement approved plan: {plan.title[:40]}",
        )
        await self.event_bus.publish(
            implementation_chat_id,
            {"type": "message", "payload": {"message": message_out.model_dump()}},
        )
        await self.event_bus.publish(
            implementation_chat_id,
            {"type": "checkpoint", "payload": {"checkpoint": checkpoint_out.model_dump()}},
        )
        updated = await plan_svc.mark_plan_status(
            chat_id=chat_id,
            plan_id=plan_id,
            status="implementing",
            approved_action=action,
            implementation_chat_id=implementation_chat_id,
        )
        _schedule_background_task(
            chat_id=implementation_chat_id,
            checkpoint_id=checkpoint_out.id,
            content=kickoff_content,
            mode="default",
            active_plan_id=None,
            session_factory=get_sessionmaker(),
            event_bus=self.event_bus,
            task_manager=self.task_manager,
        )
        return ApprovePlanResponse(
            plan=updated,
            implementationChatId=implementation_chat_id,
        )

    def get_chat_history(self, chat_id: str) -> GetChatHistoryResponse:
        project_repo = ProjectRepository(self.repo.db)
        assembler = ChatHistoryAssembler(
            self.repo, project_repo, self.settings_service
        )
        return assembler.assemble(chat_id)

    def get_chat_debug(self, chat_id: str) -> dict:
        """Assemble a debug dump of prompts and API payload for the current conversation."""
        history = self.get_chat_history(chat_id)
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        project_repo = ProjectRepository(self.repo.db)
        project_model = project_repo.get_project(chat.project_id)
        project_path = project_model.path if project_model else None

        messages = self.repo.list_messages(chat_id)
        tool_calls = self.repo.list_tool_calls(chat_id)
        mentioned_by_checkpoint = self._extract_mentioned_tool_calls_by_checkpoint(tool_calls)

        openrouter_messages: list[dict] = []
        for m in messages:
            role = "assistant" if m.role == "assistant" else "user"
            message_content = m.content
            if role == "user" and m.checkpoint_id:
                referenced_paths: list[str] = []
                for _, path in mentioned_by_checkpoint.get(m.checkpoint_id, []):
                    if path not in referenced_paths:
                        referenced_paths.append(path)
                if referenced_paths:
                    refs_inline = " ".join(
                        f"<File reference: {path} do not re-read file>" for path in referenced_paths
                    )
                    message_content = (
                        f"{message_content}\n{refs_inline}" if message_content else refs_inline
                    )
            openrouter_messages.append({"role": role, "content": message_content})
            if role != "user" or not m.checkpoint_id:
                continue
            mentioned_tool_calls = mentioned_by_checkpoint.get(m.checkpoint_id, [])
            for tc, path in mentioned_tool_calls:
                model_args_json = json.dumps({"path": path}, separators=(",", ":"))
                openrouter_messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": "read_file", "arguments": model_args_json},
                            }
                        ],
                    }
                )
                openrouter_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tc.output_text or "",
                    }
                )
        openrouter_messages = apply_initial_information(
            openrouter_messages,
            project_path=project_path,
            model=history.model,
        )
        system_prompt = self.settings_service.get_system_prompt()
        openrouter_messages.insert(0, {"role": "system", "content": system_prompt})

        return {
            "chatId": chat_id,
            "model": history.model,
            "contextLimit": history.maxTokens,
            "systemPrompt": system_prompt,
            "assembledMessages": openrouter_messages,
            "history": history.model_dump(),
        }


def _schedule_background_task(
    *,
    chat_id: str,
    checkpoint_id: str,
    content: str,
    mode: str,
    active_plan_id: str | None,
    session_factory,
    event_bus: EventBus,
    task_manager: AgentTaskManager,
    extra_messages: list[dict] | None = None,
) -> None:
    """Create and track a background asyncio task for a single agent turn."""

    async def _run() -> None:
        try:
            await asyncio.sleep(0)
            follow_up = await run_agent_turn(
                chat_id=chat_id,
                checkpoint_id=checkpoint_id,
                content=content,
                session_factory=session_factory,
                event_bus=event_bus,
                mode=mode,
                active_plan_id=active_plan_id,
                extra_messages=extra_messages,
            )
            if follow_up is not None:
                # Verification issues found — schedule the fix turn
                _schedule_background_task(
                    chat_id=chat_id,
                    checkpoint_id=follow_up.checkpoint_id,
                    content=follow_up.content,
                    mode="default",
                    active_plan_id=None,
                    extra_messages=None,
                    session_factory=session_factory,
                    event_bus=event_bus,
                    task_manager=task_manager,
                )
        except asyncio.CancelledError:
            logger.info(
                "Conversation ended: task cancelled chat_id=%s checkpoint_id=%s",
                chat_id,
                checkpoint_id,
            )
            await event_bus.publish(
                chat_id,
                {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
            )
        except Exception as exc:
            err_msg = _format_runtime_error(exc)
            logger.exception(
                "Background runtime task failed for chat_id=%s checkpoint_id=%s",
                chat_id,
                checkpoint_id,
            )
            logger.info(
                "Conversation ended: error chat_id=%s checkpoint_id=%s reason=%s",
                chat_id,
                checkpoint_id,
                err_msg,
            )
            await event_bus.publish(
                chat_id,
                {
                    "type": "message",
                    "payload": {
                        "message": {
                            "id": generate_id("msg"),
                            "role": "agent",
                            "content": f"Error: {err_msg}",
                            "timestamp": utc_now_iso(),
                            "checkpointId": checkpoint_id,
                        }
                    },
                },
            )
            await event_bus.publish(
                chat_id,
                {
                    "type": "error",
                    "payload": {
                        "message": err_msg,
                        "checkpointId": checkpoint_id,
                        "source": "backend",
                    },
                },
            )
            await event_bus.publish(
                chat_id,
                {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
            )

    task = asyncio.create_task(_run())
    task_manager.set(chat_id, task)

    def _on_done(t: asyncio.Task) -> None:
        # Only remove if this task is still the tracked one; avoids
        # a race where a stale callback removes a newer task.
        task_manager.delete_if_current(chat_id, t)

    task.add_done_callback(_on_done)
