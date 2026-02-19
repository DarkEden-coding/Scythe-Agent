import asyncio
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.db.session import get_sessionmaker
from app.initial_information import apply_initial_information
from app.tools.openrouter_format import get_openrouter_tools
from app.schemas.chat import (
    CheckpointOut,
    EditMessageResponse,
    GetChatHistoryResponse,
    MessageOut,
    SendMessageResponse,
)
from app.services.agent_loop import AgentLoop
from app.services.api_key_resolver import APIKeyResolver
from app.services.post_agent_verifier import (
    is_verification_message,
    format_message_for_agent,
    run_verification,
)
from app.services.chat_history import ChatHistoryAssembler
from app.services.approval_service import ApprovalService
from app.services.event_bus import EventBus, get_event_bus
from app.services.revert_service import RevertService
from app.services.settings_service import SettingsService
from app.utils.ids import generate_id
from app.utils.mappers import map_role_for_ui
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)

# Maps chat_id → running agent asyncio.Task (for cancellation on edit)
_running_tasks: dict[str, asyncio.Task] = {}


class ChatService:
    def __init__(self, db: Session, event_bus: EventBus | None = None):
        self.repo = ChatRepository(db)
        self.settings_repo = SettingsRepository(db)
        self.settings_service = SettingsService(db)
        self.event_bus = event_bus or get_event_bus()

    async def _deny_pending_and_cancel_agent(
        self, chat_id: str, reject_reason: str = "User sent new message"
    ) -> bool:
        """Deny any pending tool approvals and cancel the running agent for this chat.
        Returns True if a task was cancelled."""
        existing_task = _running_tasks.pop(chat_id, None)
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

        self._schedule_runtime(
            chat_id=chat_id,
            checkpoint_id=checkpoint.id,
            content=content,
        )
        return SendMessageResponse(message=message_out, checkpoint=checkpoint_out)

    def _schedule_runtime(
        self,
        *,
        chat_id: str,
        checkpoint_id: str,
        content: str,
    ) -> None:
        event_bus = self.event_bus

        async def _runtime_pass() -> None:
            try:
                await asyncio.sleep(0)
                app_settings = get_settings()
                max_iterations = app_settings.max_agent_iterations
                with get_sessionmaker()() as bg_session:
                    bg_settings_repo = SettingsRepository(bg_session)
                    bg_settings_svc = SettingsService(bg_session)
                    default_prompt = bg_settings_svc.get_system_prompt()
                    loop = AgentLoop(
                        chat_repo=ChatRepository(bg_session),
                        project_repo=ProjectRepository(bg_session),
                        settings_repo=bg_settings_repo,
                        settings_service=bg_settings_svc,
                        api_key_resolver=APIKeyResolver(bg_settings_repo),
                        approval_svc=ApprovalService(bg_session, event_bus=event_bus),
                        event_bus=event_bus,
                        apply_initial_information=apply_initial_information,
                        get_openrouter_tools=get_openrouter_tools,
                        default_system_prompt=default_prompt,
                        session_factory=get_sessionmaker(),
                    )
                    await loop.run(
                        chat_id=chat_id,
                        checkpoint_id=checkpoint_id,
                        content=content,
                        max_iterations=max_iterations,
                    )

                    # Post-agent verification: run checks on edited files
                    if not is_verification_message(content):
                        chat_repo = ChatRepository(bg_session)
                        project_repo = ProjectRepository(bg_session)
                        chat_model = chat_repo.get_chat(chat_id)
                        if chat_model:
                            project = project_repo.get_project(chat_model.project_id)
                            project_path = project.path if project else None
                            if project_path:
                                edits = chat_repo.list_file_edits_for_checkpoint(
                                    chat_id, checkpoint_id
                                )
                                if edits:
                                    edited_paths = list(
                                        {str(Path(e.file_path).resolve()) for e in edits}
                                    )
                                    issues, summary, by_tool = await run_verification(
                                        edited_paths, project_path
                                    )
                                    if issues:
                                        verification_content = format_message_for_agent(
                                            issues
                                        )
                                        ts = utc_now_iso()
                                        fix_msg = chat_repo.create_message(
                                            message_id=generate_id("msg"),
                                            chat_id=chat_id,
                                            role="user",
                                            content=verification_content,
                                            timestamp=ts,
                                            checkpoint_id=None,
                                        )
                                        fix_cp = chat_repo.create_checkpoint(
                                            checkpoint_id=generate_id("cp"),
                                            chat_id=chat_id,
                                            message_id=fix_msg.id,
                                            label="Verification issues found",
                                            timestamp=ts,
                                        )
                                        chat_repo.link_message_checkpoint(
                                            fix_msg, fix_cp.id
                                        )
                                        chat_repo.update_chat_timestamp(
                                            chat_model, ts
                                        )
                                        chat_repo.commit()

                                        msg_out = MessageOut(
                                            id=fix_msg.id,
                                            role="user",
                                            content=fix_msg.content,
                                            timestamp=fix_msg.timestamp,
                                            checkpointId=fix_cp.id,
                                        )
                                        cp_out = CheckpointOut(
                                            id=fix_cp.id,
                                            messageId=fix_cp.message_id,
                                            timestamp=fix_cp.timestamp,
                                            label=fix_cp.label,
                                            fileEdits=[],
                                            toolCalls=[],
                                            reasoningBlocks=[],
                                        )
                                        await event_bus.publish(
                                            chat_id,
                                            {
                                                "type": "checkpoint",
                                                "payload": {
                                                    "checkpoint": cp_out.model_dump()
                                                },
                                            },
                                        )
                                        await event_bus.publish(
                                            chat_id,
                                            {
                                                "type": "message",
                                                "payload": {
                                                    "message": msg_out.model_dump()
                                                },
                                            },
                                        )
                                        await event_bus.publish(
                                            chat_id,
                                            {
                                                "type": "verification_issues",
                                                "payload": {
                                                    "checkpointId": checkpoint_id,
                                                    "summary": summary,
                                                    "issueCount": len(issues),
                                                    "fileCount": len(
                                                        {i.file for i in issues}
                                                    ),
                                                    "byTool": by_tool,
                                                },
                                            },
                                        )
                                        self._schedule_runtime(
                                            chat_id=chat_id,
                                            checkpoint_id=fix_cp.id,
                                            content=verification_content,
                                        )
                                        return

                    # agent_done already published by AgentLoop
            except Exception as exc:
                err_msg = str(exc)
                logger.exception(
                    "Background runtime task failed for chat_id=%s checkpoint_id=%s",
                    chat_id,
                    checkpoint_id,
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

        task = asyncio.create_task(_runtime_pass())
        _running_tasks[chat_id] = task

        def _on_done(t: asyncio.Task) -> None:
            _running_tasks.pop(chat_id, None)

        task.add_done_callback(_on_done)

    async def edit_message(self, chat_id: str, message_id: str, content: str) -> EditMessageResponse:
        message = self.repo.get_message(message_id)
        if message is None or message.chat_id != chat_id:
            raise ValueError(f"Message not found: {message_id}")
        if message.role != "user":
            raise ValueError("Only user messages can be edited")

        checkpoint = self.repo.get_checkpoint_by_message(message_id)
        if checkpoint is None:
            raise ValueError(f"No checkpoint found for message: {message_id}")

        # Cancel any running agent task for this chat
        existing_task = _running_tasks.pop(chat_id, None)
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

        self._schedule_runtime(
            chat_id=chat_id,
            checkpoint_id=checkpoint.id,
            content=content,
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
