from datetime import datetime

from sqlalchemy import and_, delete, or_
from sqlalchemy import select

from app.db.models.chat import Chat
from app.db.models.checkpoint import Checkpoint
from app.db.models.context_item import ContextItem
from app.db.models.file_edit import FileEdit
from app.db.models.file_snapshot import FileSnapshot
from app.db.models.message import Message
from app.db.models.reasoning_block import ReasoningBlock
from app.db.models.tool_call import ToolCall
from app.db.repositories.base_repo import BaseRepository


def _normalize_ts(iso_str: str) -> str:
    """Ensure ISO timestamp has consistent microsecond padding for string comparison."""
    dt = datetime.fromisoformat(iso_str)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


class ChatRepository(BaseRepository):
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
        stmt = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.timestamp.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_tool_calls(self, chat_id: str) -> list[ToolCall]:
        stmt = (
            select(ToolCall)
            .where(ToolCall.chat_id == chat_id)
            .order_by(ToolCall.timestamp.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_file_edits(self, chat_id: str) -> list[FileEdit]:
        stmt = (
            select(FileEdit)
            .where(FileEdit.chat_id == chat_id)
            .order_by(FileEdit.timestamp.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_file_edits_for_checkpoint(
        self, chat_id: str, checkpoint_id: str
    ) -> list[FileEdit]:
        stmt = (
            select(FileEdit)
            .where(
                FileEdit.chat_id == chat_id,
                FileEdit.checkpoint_id == checkpoint_id,
            )
            .order_by(FileEdit.timestamp.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_checkpoints(self, chat_id: str) -> list[Checkpoint]:
        stmt = (
            select(Checkpoint)
            .where(Checkpoint.chat_id == chat_id)
            .order_by(Checkpoint.timestamp.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_reasoning_blocks(self, chat_id: str) -> list[ReasoningBlock]:
        stmt = (
            select(ReasoningBlock)
            .where(ReasoningBlock.chat_id == chat_id)
            .order_by(ReasoningBlock.timestamp.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_context_items(self, chat_id: str) -> list[ContextItem]:
        stmt = (
            select(ContextItem)
            .where(ContextItem.chat_id == chat_id)
            .order_by(ContextItem.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def replace_context_items(
        self, chat_id: str, items: list[tuple[str, str, str, int]]
    ) -> None:
        """Replace all context items with (id, type, label, tokens) tuples."""
        self.db.execute(delete(ContextItem).where(ContextItem.chat_id == chat_id))
        for item_id, item_type, label, tokens in items:
            self.db.add(
                ContextItem(
                    id=item_id,
                    chat_id=chat_id,
                    type=item_type,
                    label=label,
                    tokens=tokens,
                )
            )

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
        parallel_group: str | None = None,
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
            parallel=1 if parallel_group else 0,
            parallel_group=parallel_group,
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
        output_file_path: str | None = None,
        duration_ms: int | None = None,
    ) -> ToolCall:
        tool_call.status = status
        if output_text is not None:
            tool_call.output_text = output_text
        if output_file_path is not None:
            tool_call.output_file_path = output_file_path
        if duration_ms is not None:
            tool_call.duration_ms = duration_ms
        return tool_call

    def link_message_checkpoint(self, message: Message, checkpoint_id: str) -> None:
        message.checkpoint_id = checkpoint_id

    def create_reasoning_block(
        self,
        *,
        reasoning_block_id: str,
        chat_id: str,
        checkpoint_id: str | None,
        content: str,
        timestamp: str,
        duration_ms: int | None = None,
    ) -> ReasoningBlock:
        block = ReasoningBlock(
            id=reasoning_block_id,
            chat_id=chat_id,
            checkpoint_id=checkpoint_id,
            content=content,
            timestamp=timestamp,
            duration_ms=duration_ms,
        )
        self.db.add(block)
        return block

    def get_checkpoint_by_message(self, message_id: str) -> Checkpoint | None:
        stmt = select(Checkpoint).where(Checkpoint.message_id == message_id)
        return self.db.scalars(stmt).first()

    def create_file_snapshot(
        self,
        *,
        snapshot_id: str,
        chat_id: str,
        checkpoint_id: str | None,
        file_edit_id: str | None,
        file_path: str,
        content: str | None,
        timestamp: str,
    ) -> FileSnapshot:
        snapshot = FileSnapshot(
            id=snapshot_id,
            chat_id=chat_id,
            checkpoint_id=checkpoint_id,
            file_edit_id=file_edit_id,
            file_path=file_path,
            content=content,
            timestamp=timestamp,
        )
        self.db.add(snapshot)
        return snapshot

    def get_file_snapshot_by_edit(self, file_edit_id: str) -> FileSnapshot | None:
        stmt = select(FileSnapshot).where(FileSnapshot.file_edit_id == file_edit_id)
        return self.db.scalars(stmt).first()

    def list_file_snapshots_after_checkpoint(
        self, chat_id: str, cutoff_ts: str, checkpoint_id: str
    ) -> list[FileSnapshot]:
        cutoff = _normalize_ts(cutoff_ts)
        stmt = (
            select(FileSnapshot)
            .where(
                FileSnapshot.chat_id == chat_id,
                or_(
                    FileSnapshot.timestamp > cutoff,
                    and_(
                        FileSnapshot.timestamp == cutoff,
                        or_(FileSnapshot.checkpoint_id.is_(None), FileSnapshot.checkpoint_id != checkpoint_id),
                    ),
                ),
            )
            .order_by(FileSnapshot.timestamp.desc())
        )
        return list(self.db.scalars(stmt).all())

    def delete_file_snapshots_after_checkpoint(
        self, chat_id: str, cutoff_ts: str, checkpoint_id: str
    ) -> None:
        cutoff = _normalize_ts(cutoff_ts)
        self.db.execute(
            delete(FileSnapshot).where(
                FileSnapshot.chat_id == chat_id,
                or_(
                    FileSnapshot.timestamp > cutoff,
                    and_(
                        FileSnapshot.timestamp == cutoff,
                        or_(FileSnapshot.checkpoint_id.is_(None), FileSnapshot.checkpoint_id != checkpoint_id),
                    ),
                ),
            )
        )

    def delete_file_snapshot(self, snapshot: FileSnapshot) -> None:
        self.db.delete(snapshot)

    def list_tool_calls_after_checkpoint(
        self, chat_id: str, cutoff_timestamp: str, checkpoint_id: str
    ) -> list[ToolCall]:
        cutoff = _normalize_ts(cutoff_timestamp)
        stmt = (
            select(ToolCall)
            .where(
                ToolCall.chat_id == chat_id,
                or_(
                    ToolCall.timestamp > cutoff,
                    and_(
                        ToolCall.timestamp == cutoff,
                        or_(ToolCall.checkpoint_id.is_(None), ToolCall.checkpoint_id != checkpoint_id),
                    ),
                ),
            )
        )
        return list(self.db.scalars(stmt).all())

    def delete_file_edit(self, file_edit: FileEdit) -> None:
        self.db.delete(file_edit)

    def delete_after_checkpoint(
        self, *, chat_id: str, cutoff_timestamp: str, checkpoint_id: str
    ) -> None:
        cutoff = _normalize_ts(cutoff_timestamp)
        # Delete records that are strictly after the cutoff, OR have the same
        # timestamp but do not belong to the checkpoint being reverted to.
        self.db.execute(
            delete(Message).where(
                Message.chat_id == chat_id,
                or_(
                    Message.timestamp > cutoff,
                    and_(
                        Message.timestamp == cutoff,
                        or_(Message.checkpoint_id.is_(None), Message.checkpoint_id != checkpoint_id),
                    ),
                ),
            )
        )
        self.db.execute(
            delete(ToolCall).where(
                ToolCall.chat_id == chat_id,
                or_(
                    ToolCall.timestamp > cutoff,
                    and_(
                        ToolCall.timestamp == cutoff,
                        or_(ToolCall.checkpoint_id.is_(None), ToolCall.checkpoint_id != checkpoint_id),
                    ),
                ),
            )
        )
        self.db.execute(
            delete(FileEdit).where(
                FileEdit.chat_id == chat_id,
                or_(
                    FileEdit.timestamp > cutoff,
                    and_(
                        FileEdit.timestamp == cutoff,
                        or_(FileEdit.checkpoint_id.is_(None), FileEdit.checkpoint_id != checkpoint_id),
                    ),
                ),
            )
        )
        self.db.execute(
            delete(ReasoningBlock).where(
                ReasoningBlock.chat_id == chat_id,
                or_(
                    ReasoningBlock.timestamp > cutoff,
                    and_(
                        ReasoningBlock.timestamp == cutoff,
                        or_(ReasoningBlock.checkpoint_id.is_(None), ReasoningBlock.checkpoint_id != checkpoint_id),
                    ),
                ),
            )
        )
        self.db.execute(
            delete(Checkpoint).where(
                Checkpoint.chat_id == chat_id,
                or_(
                    Checkpoint.timestamp > cutoff,
                    and_(
                        Checkpoint.timestamp == cutoff, Checkpoint.id != checkpoint_id
                    ),
                ),
            )
        )
