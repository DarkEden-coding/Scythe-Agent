import asyncio
import logging

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.db.session import get_sessionmaker
from app.initial_information import apply_initial_information
from app.preprocessors.system_prompt import DEFAULT_SYSTEM_PROMPT
from app.tools.openrouter_format import get_openrouter_tools
from app.schemas.chat import (
    CheckpointOut,
    GetChatHistoryResponse,
    MessageOut,
    SendMessageResponse,
)
from app.services.agent_loop import AgentLoop
from app.services.api_key_resolver import APIKeyResolver
from app.services.chat_history import ChatHistoryAssembler
from app.services.approval_service import ApprovalService
from app.services.event_bus import EventBus, get_event_bus
from app.services.settings_service import SettingsService
from app.utils.ids import generate_id
from app.utils.mappers import map_role_for_ui
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, db: Session, event_bus: EventBus | None = None):
        self.repo = ChatRepository(db)
        self.settings_repo = SettingsRepository(db)
        self.settings_service = SettingsService(db)
        self.event_bus = event_bus or get_event_bus()

    async def send_message(self, chat_id: str, content: str) -> SendMessageResponse:
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

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
                    loop = AgentLoop(
                        chat_repo=ChatRepository(bg_session),
                        project_repo=ProjectRepository(bg_session),
                        settings_repo=bg_settings_repo,
                        settings_service=SettingsService(bg_session),
                        api_key_resolver=APIKeyResolver(bg_settings_repo),
                        approval_svc=ApprovalService(bg_session, event_bus=event_bus),
                        event_bus=event_bus,
                        apply_initial_information=apply_initial_information,
                        get_openrouter_tools=get_openrouter_tools,
                        default_system_prompt=DEFAULT_SYSTEM_PROMPT,
                    )
                    await loop.run(
                        chat_id=chat_id,
                        checkpoint_id=checkpoint_id,
                        content=content,
                        max_iterations=max_iterations,
                    )
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

        _ = asyncio.create_task(_runtime_pass())

    def get_chat_history(self, chat_id: str) -> GetChatHistoryResponse:
        assembler = ChatHistoryAssembler(self.repo, self.settings_service)
        return assembler.assemble(chat_id)
