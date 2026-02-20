import asyncio
import json
import logging

import httpx
from sqlalchemy.orm import Session

from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.db.session import get_sessionmaker
from app.initial_information import apply_initial_information
from app.schemas.chat import (
    ContinueAgentResponse,
    CheckpointOut,
    EditMessageResponse,
    GetChatHistoryResponse,
    MessageOut,
    SendMessageResponse,
)
from app.services.approval_service import ApprovalService
from app.services.agent_task_manager import AgentTaskManager, get_agent_task_manager
from app.services.chat_history import ChatHistoryAssembler
from app.services.event_bus import EventBus, get_event_bus
from app.services.memory.observational.background import get_om_background_runner
from app.services.revert_service import RevertService
from app.services.runtime_orchestrator import run_agent_turn
from app.services.settings_service import SettingsService
from app.utils.ids import generate_id
from app.utils.mappers import map_role_for_ui
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)


def _extract_http_error_detail(body: object) -> str:
    """Best-effort extraction of a useful provider error message from JSON/text bodies."""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            msg = err.get("message")
            typ = err.get("type")
            param = err.get("param")
            parts = [str(msg).strip()] if isinstance(msg, str) and str(msg).strip() else []
            if isinstance(typ, str) and typ.strip():
                parts.append(f"type={typ.strip()}")
            if isinstance(param, str) and param.strip():
                parts.append(f"param={param.strip()}")
            if parts:
                return " | ".join(parts)
        msg = body.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()
        detail = body.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if isinstance(detail, list):
            joined = ", ".join(str(x).strip() for x in detail if str(x).strip())
            if joined:
                return joined
        try:
            compact = json.dumps(body, separators=(",", ":"), ensure_ascii=True)
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

    async def _deny_pending_and_cancel_agent(
        self, chat_id: str, reject_reason: str = "User sent new message"
    ) -> bool:
        """Deny any pending tool approvals and cancel the running agent for this chat.
        Returns True if a task was cancelled."""
        # Cancel any in-flight observation cycle for this chat.
        get_om_background_runner().cancel(chat_id)

        existing_task = self.task_manager.pop(chat_id)
        if existing_task is None or existing_task.done():
            return False
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
        return True

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

        _schedule_background_task(
            chat_id=chat_id,
            checkpoint_id=checkpoint.id,
            content=content,
            session_factory=get_sessionmaker(),
            event_bus=self.event_bus,
            task_manager=self.task_manager,
        )
        return ContinueAgentResponse(started=True, checkpointId=checkpoint.id)

    async def send_message(self, chat_id: str, content: str) -> SendMessageResponse:
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        await self._deny_pending_and_cancel_agent(chat_id)

        existing_messages = self.repo.list_messages(chat_id)
        is_first_message = len(existing_messages) == 0
        if is_first_message and chat.title == "New chat":
            title = content.strip()[:64] or "New chat"
            chat.title = title

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
            label=f"User message: {content[:48]}",
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
            session_factory=get_sessionmaker(),
            event_bus=self.event_bus,
            task_manager=self.task_manager,
        )
        return SendMessageResponse(message=message_out, checkpoint=checkpoint_out)

    async def edit_message(self, chat_id: str, message_id: str, content: str) -> EditMessageResponse:
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

        # Update message content and checkpoint label in-place
        message = self.repo.get_message(message_id)
        if message is not None:
            message.content = content
        cp = self.repo.get_checkpoint(checkpoint.id)
        if cp is not None:
            cp.label = f"User message: {content[:48]}"
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
                },
            },
        )

        _schedule_background_task(
            chat_id=chat_id,
            checkpoint_id=checkpoint.id,
            content=content,
            session_factory=get_sessionmaker(),
            event_bus=self.event_bus,
            task_manager=self.task_manager,
        )
        return EditMessageResponse(revertedHistory=reverted)

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
        openrouter_messages = [
            {"role": "assistant" if m.role == "assistant" else "user", "content": m.content}
            for m in messages
        ]
        openrouter_messages = apply_initial_information(
            openrouter_messages, project_path=project_path
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
    session_factory,
    event_bus: EventBus,
    task_manager: AgentTaskManager,
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
            )
            if follow_up is not None:
                # Verification issues found — schedule the fix turn
                _schedule_background_task(
                    chat_id=chat_id,
                    checkpoint_id=follow_up.checkpoint_id,
                    content=follow_up.content,
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
