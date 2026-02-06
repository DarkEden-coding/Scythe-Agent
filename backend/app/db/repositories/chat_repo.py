import json
from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.chat import Chat
from app.db.models.checkpoint import Checkpoint
from app.db.models.context_item import ContextItem
from app.db.models.file_edit import FileEdit
from app.db.models.message import Message
from app.db.models.reasoning_block import ReasoningBlock
from app.db.models.tool_call import ToolCall


class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_chat(self, chat_id: str) -> Chat | None:
        return self.db.get(Chat, chat_id)

    def get_message(self, message_id: str) -> Message | None:
        return self.db.get(Message, message_id)

    def get_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        return self.db.get(Checkpoint, checkpoint_id)

    def get_tool_call(self, tool_call_id: str) -> ToolCall | None:
        return self.db.get(ToolCall, tool_call_id)

    def get_file_edit(self, file_edit_id: str) -> FileEdit | None:
        return self.db.get(FileEdit, file_edit_id)

    def list_messages(self, chat_id: str) -> list[Message]:
        stmt = select(Message).where(Message.chat_id == chat_id).order_by(Message.timestamp.asc())
        return list(self.db.scalars(stmt).all())

    def list_tool_calls(self, chat_id: str) -> list[ToolCall]:
        stmt = select(ToolCall).where(ToolCall.chat_id == chat_id).order_by(ToolCall.timestamp.asc())
        return list(self.db.scalars(stmt).all())

    def list_file_edits(self, chat_id: str) -> list[FileEdit]:
        stmt = select(FileEdit).where(FileEdit.chat_id == chat_id).order_by(FileEdit.timestamp.asc())
        return list(self.db.scalars(stmt).all())

    def list_checkpoints(self, chat_id: str) -> list[Checkpoint]:
        stmt = select(Checkpoint).where(Checkpoint.chat_id == chat_id).order_by(Checkpoint.timestamp.asc())
        return list(self.db.scalars(stmt).all())

    def list_reasoning_blocks(self, chat_id: str) -> list[ReasoningBlock]:
        stmt = select(ReasoningBlock).where(ReasoningBlock.chat_id == chat_id).order_by(ReasoningBlock.timestamp.asc())
        return list(self.db.scalars(stmt).all())

    def list_context_items(self, chat_id: str) -> list[ContextItem]:
        stmt = select(ContextItem).where(ContextItem.chat_id == chat_id).order_by(ContextItem.id.asc())
        return list(self.db.scalars(stmt).all())

    def create_message(
        self,
        *,
        message_id: str,
        chat_id: str,
        role: str,
        content: str,
        timestamp: str,
        checkpoint_id: str | None = None,
    ) -> Message:
        message = Message(
            id=message_id,
            chat_id=chat_id,
            role=role,
            content=content,
            timestamp=timestamp,
            checkpoint_id=checkpoint_id,
        )
        self.db.add(message)
        return message

    def create_checkpoint(
        self,
        *,
        checkpoint_id: str,
        chat_id: str,
        message_id: str,
        label: str,
        timestamp: str,
    ) -> Checkpoint:
        checkpoint = Checkpoint(
            id=checkpoint_id,
            chat_id=chat_id,
            message_id=message_id,
            label=label,
            timestamp=timestamp,
        )
        self.db.add(checkpoint)
        return checkpoint

    def create_tool_call(
        self,
        *,
        tool_call_id: str,
        chat_id: str,
        checkpoint_id: str | None,
        name: str,
        status: str,
        input_json: str,
        timestamp: str,
        output_text: str | None = None,
        duration_ms: int | None = None,
    ) -> ToolCall:
        tool_call = ToolCall(
            id=tool_call_id,
            chat_id=chat_id,
            checkpoint_id=checkpoint_id,
            name=name,
            status=status,
            input_json=input_json,
            output_text=output_text,
            timestamp=timestamp,
            duration_ms=duration_ms,
            parallel=0,
            parallel_group=None,
        )
        self.db.add(tool_call)
        return tool_call

    def create_file_edit(
        self,
        *,
        file_edit_id: str,
        chat_id: str,
        checkpoint_id: str,
        file_path: str,
        action: str,
        diff: str | None,
        timestamp: str,
    ) -> FileEdit:
        edit = FileEdit(
            id=file_edit_id,
            chat_id=chat_id,
            checkpoint_id=checkpoint_id,
            file_path=file_path,
            action=action,
            diff=diff,
            timestamp=timestamp,
        )
        self.db.add(edit)
        return edit

    def update_chat_timestamp(self, chat: Chat, timestamp: str) -> None:
        chat.updated_at = timestamp

    def update_context_tokens(self, context_item: ContextItem, tokens: int) -> None:
        context_item.tokens = tokens

    def set_tool_call_status(
        self,
        tool_call: ToolCall,
        *,
        status: str,
        output_text: str | None = None,
        duration_ms: int | None = None,
    ) -> ToolCall:
        tool_call.status = status
        if output_text is not None:
            tool_call.output_text = output_text
        if duration_ms is not None:
            tool_call.duration_ms = duration_ms
        return tool_call

    def link_message_checkpoint(self, message: Message, checkpoint_id: str) -> None:
        message.checkpoint_id = checkpoint_id

    def delete_file_edit(self, file_edit: FileEdit) -> None:
        self.db.delete(file_edit)

    def delete_after_checkpoint(self, *, chat_id: str, cutoff_timestamp: str) -> None:
        self.db.execute(
            delete(Message).where(Message.chat_id == chat_id, Message.timestamp > cutoff_timestamp)
        )
        self.db.execute(
            delete(ToolCall).where(ToolCall.chat_id == chat_id, ToolCall.timestamp > cutoff_timestamp)
        )
        self.db.execute(
            delete(FileEdit).where(FileEdit.chat_id == chat_id, FileEdit.timestamp > cutoff_timestamp)
        )
        self.db.execute(
            delete(ReasoningBlock).where(ReasoningBlock.chat_id == chat_id, ReasoningBlock.timestamp > cutoff_timestamp)
        )
        self.db.execute(
            delete(Checkpoint).where(Checkpoint.chat_id == chat_id, Checkpoint.timestamp > cutoff_timestamp)
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def parse_input_json(raw: str) -> dict:
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
