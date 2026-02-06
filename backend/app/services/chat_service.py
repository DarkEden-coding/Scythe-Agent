import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.serializers.compat import map_file_action_for_ui, map_role_for_ui
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
from app.services.event_bus import EventBus, get_event_bus
from app.services.runtime_service import RuntimeService
from app.services.settings_service import SettingsService


class ChatService:
    def __init__(self, db: Session, event_bus: EventBus | None = None):
        self.repo = ChatRepository(db)
        self.settings_repo = SettingsRepository(db)
        self.settings_service = SettingsService(db)
        self.event_bus = event_bus or get_event_bus()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}-{uuid4().hex[:12]}"

    async def send_message(self, chat_id: str, content: str) -> SendMessageResponse:
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        timestamp = self._now()
        message = self.repo.create_message(
            message_id=self._new_id("msg"),
            chat_id=chat_id,
            role="user",
            content=content,
            timestamp=timestamp,
            checkpoint_id=None,
        )
        checkpoint = self.repo.create_checkpoint(
            checkpoint_id=self._new_id("cp"),
            chat_id=chat_id,
            message_id=message.id,
            label=f"User message: {content[:48]}",
            timestamp=timestamp,
        )
        self.repo.link_message_checkpoint(message, checkpoint.id)
        self.repo.update_chat_timestamp(chat, timestamp)
        pending_tool = self.repo.create_tool_call(
            tool_call_id=self._new_id("tc"),
            chat_id=chat_id,
            checkpoint_id=checkpoint.id,
            name="read_file",
            status="pending",
            input_json=json.dumps({"path": "plans/backend-python-mvp-plan.md"}),
            timestamp=timestamp,
        )
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
            tool_call_id=pending_tool.id,
            tool_name=pending_tool.name,
            tool_input=self.repo.parse_input_json(pending_tool.input_json),
        )
        return SendMessageResponse(message=message_out, checkpoint=checkpoint_out)

    def _schedule_runtime(
        self,
        *,
        chat_id: str,
        checkpoint_id: str,
        content: str,
        tool_call_id: str,
        tool_name: str,
        tool_input: dict,
    ) -> None:
        async def _runtime_pass() -> None:
            await asyncio.sleep(0)
            settings = self.settings_service.get_settings()
            plan_summary = await RuntimeService().plan_response(model=settings.model, user_content=content)
            auto_approved = self._is_auto_approved(tool_name=tool_name, input_payload=tool_input)
            description = f"Proposed from runtime scaffold for: {content[:32]} (checkpoint {checkpoint_id})"
            if plan_summary:
                description = f"{description}; planner={plan_summary[:120]}"
            await self.event_bus.publish(
                chat_id,
                {
                    "type": "approval_required",
                    "payload": {
                        "toolCallId": tool_call_id,
                        "toolName": tool_name,
                        "input": tool_input,
                        "description": description,
                        "autoApproved": auto_approved,
                    },
                },
            )

        asyncio.create_task(_runtime_pass())

    def _is_auto_approved(self, *, tool_name: str, input_payload: dict) -> bool:
        path_value = str(input_payload.get("path", ""))
        extension = ""
        if "." in path_value:
            extension = "." + path_value.rsplit(".", maxsplit=1)[1]
        directory = path_value.rsplit("/", maxsplit=1)[0] if "/" in path_value else ""
        payload_text = json.dumps(input_payload)
        rules = self.settings_repo.list_auto_approve_rules()
        for rule in rules:
            if not bool(rule.enabled):
                continue
            if rule.field == "tool" and tool_name == rule.value:
                return True
            if rule.field == "path" and path_value == rule.value:
                return True
            if rule.field == "extension" and extension == rule.value:
                return True
            if rule.field == "directory" and directory.startswith(rule.value):
                return True
            if rule.field == "pattern" and rule.value in payload_text:
                return True
        return False

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

        tool_calls = [
            ToolCallOut(
                id=t.id,
                name=t.name,
                status=t.status,
                input=self.repo.parse_input_json(t.input_json),
                output=t.output_text,
                timestamp=t.timestamp,
                duration=t.duration_ms,
                isParallel=bool(t.parallel) if t.parallel is not None else None,
                parallelGroupId=t.parallel_group,
            )
            for t in self.repo.list_tool_calls(chat_id)
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
            for f in self.repo.list_file_edits(chat_id)
        ]

        checkpoints = self.repo.list_checkpoints(chat_id)
        cp_file_map: dict[str, list[str]] = {c.id: [] for c in checkpoints}
        cp_tool_map: dict[str, list[str]] = {c.id: [] for c in checkpoints}
        cp_reason_map: dict[str, list[str]] = {c.id: [] for c in checkpoints}

        for t in self.repo.list_tool_calls(chat_id):
            if t.checkpoint_id and t.checkpoint_id in cp_tool_map:
                cp_tool_map[t.checkpoint_id].append(t.id)
        for f in self.repo.list_file_edits(chat_id):
            if f.checkpoint_id in cp_file_map:
                cp_file_map[f.checkpoint_id].append(f.id)
        for r in self.repo.list_reasoning_blocks(chat_id):
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
            for r in self.repo.list_reasoning_blocks(chat_id)
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
