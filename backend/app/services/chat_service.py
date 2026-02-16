import asyncio
import logging

from sqlalchemy.orm import Session

from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.db.session import get_sessionmaker
from app.schemas.chat import (
    CheckpointOut,
    ContextItemOut,
    FileEditOut,
    GetChatHistoryResponse,
    MessageOut,
    ReasoningBlockOut,
    SendMessageResponse,
    ToolCallOut,
)
from app.services.approval_service import ApprovalService
from app.services.event_bus import EventBus, get_event_bus
from app.services.runtime_service import RuntimeService
from app.services.settings_service import SettingsService
from app.utils.ids import generate_id
from app.utils.json_helpers import safe_parse_json
from app.utils.mappers import map_file_action_for_ui, map_role_for_ui
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

        await self.event_bus.publish(
            chat_id,
            {"type": "message", "payload": {"message": message_out.model_dump()}},
        )
        await self.event_bus.publish(
            chat_id,
            {"type": "checkpoint", "payload": {"checkpoint": checkpoint_out.model_dump()}},
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
                with get_sessionmaker()() as bg_session:
                    bg_settings_service = SettingsService(bg_session)
                    settings = bg_settings_service.get_settings()
                    plan_summary = await RuntimeService().plan_response(
                        model=settings.model, user_content=content
                    )
                    description = f"Proposed from runtime scaffold for: {content[:32]} (checkpoint {checkpoint_id})"
                    if plan_summary:
                        description = f"{description}; planner={plan_summary[:120]}"
                    await event_bus.publish(
                        chat_id,
                        {
                            "type": "runtime_plan",
                            "payload": {
                                "checkpointId": checkpoint_id,
                                "description": description,
                            },
                        },
                    )
            except Exception:
                logger.exception(
                    "Background runtime task failed for chat_id=%s checkpoint_id=%s",
                    chat_id,
                    checkpoint_id,
                )
                await event_bus.publish(
                    chat_id,
                    {
                        "type": "error",
                        "payload": {
                            "message": "Background runtime task failed unexpectedly.",
                            "checkpointId": checkpoint_id,
                        },
                    },
                )

        asyncio.create_task(_runtime_pass())

    def _is_auto_approved(self, *, tool_name: str, input_payload: dict) -> bool:
        approval_svc = ApprovalService(self.repo.db)
        return approval_svc.should_auto_approve(tool_name, input_payload)

    def get_chat_history(self, chat_id: str) -> GetChatHistoryResponse:
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        messages = [
            MessageOut(
                id=m.id,
                role=map_role_for_ui(m.role),
                content=m.content,
                timestamp=m.timestamp,
                checkpointId=m.checkpoint_id,
            )
            for m in self.repo.list_messages(chat_id)
        ]

        raw_tool_calls = self.repo.list_tool_calls(chat_id)
        raw_file_edits = self.repo.list_file_edits(chat_id)
        raw_reasoning_blocks = self.repo.list_reasoning_blocks(chat_id)

        tool_calls = [
            ToolCallOut(
                id=t.id,
                name=t.name,
                status=t.status,
                input=safe_parse_json(t.input_json),
                output=t.output_text,
                timestamp=t.timestamp,
                duration=t.duration_ms,
                isParallel=bool(t.parallel) if t.parallel is not None else None,
                parallelGroupId=t.parallel_group,
            )
            for t in raw_tool_calls
        ]

        file_edits = [
            FileEditOut(
                id=f.id,
                filePath=f.file_path,
                action=map_file_action_for_ui(f.action),
                diff=f.diff,
                timestamp=f.timestamp,
                checkpointId=f.checkpoint_id,
            )
            for f in raw_file_edits
        ]

        checkpoints = self.repo.list_checkpoints(chat_id)
        cp_file_map: dict[str, list[str]] = {c.id: [] for c in checkpoints}
        cp_tool_map: dict[str, list[str]] = {c.id: [] for c in checkpoints}
        cp_reason_map: dict[str, list[str]] = {c.id: [] for c in checkpoints}

        for t in raw_tool_calls:
            if t.checkpoint_id and t.checkpoint_id in cp_tool_map:
                cp_tool_map[t.checkpoint_id].append(t.id)
        for f in raw_file_edits:
            if f.checkpoint_id in cp_file_map:
                cp_file_map[f.checkpoint_id].append(f.id)
        for r in raw_reasoning_blocks:
            if r.checkpoint_id in cp_reason_map:
                cp_reason_map[r.checkpoint_id].append(r.id)

        checkpoints_out = [
            CheckpointOut(
                id=c.id,
                messageId=c.message_id,
                timestamp=c.timestamp,
                label=c.label,
                fileEdits=cp_file_map.get(c.id, []),
                toolCalls=cp_tool_map.get(c.id, []),
                reasoningBlocks=cp_reason_map.get(c.id, []),
            )
            for c in checkpoints
        ]

        reasoning_blocks = [
            ReasoningBlockOut(
                id=r.id,
                content=r.content,
                timestamp=r.timestamp,
                duration=r.duration_ms,
                checkpointId=r.checkpoint_id,
            )
            for r in raw_reasoning_blocks
        ]

        context_items = [
            ContextItemOut(id=c.id, type=c.type, name=c.label, tokens=c.tokens)
            for c in self.repo.list_context_items(chat_id)
        ]

        settings = self.settings_service.get_settings()
        return GetChatHistoryResponse(
            chatId=chat_id,
            messages=messages,
            toolCalls=tool_calls,
            fileEdits=file_edits,
            checkpoints=checkpoints_out,
            reasoningBlocks=reasoning_blocks,
            contextItems=context_items,
            maxTokens=settings.contextLimit,
            model=settings.model,
        )
