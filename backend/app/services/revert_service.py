from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.repositories.chat_repo import ChatRepository
from app.schemas.chat import FileEditOut, RevertFileResponse, RevertToCheckpointResponse
from app.services.chat_history import ChatHistoryAssembler
from app.services.settings_service import SettingsService
from app.utils.mappers import map_file_action_for_ui


class RevertService:
    def __init__(self, db: Session):
        self.repo = ChatRepository(db)
        self._assembler = ChatHistoryAssembler(
            self.repo, SettingsService(db)
        )

    def revert_to_checkpoint(self, chat_id: str, checkpoint_id: str) -> RevertToCheckpointResponse:
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        checkpoint = self.repo.get_checkpoint(checkpoint_id)
        if checkpoint is None or checkpoint.chat_id != chat_id:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        self.repo.delete_after_checkpoint(
            chat_id=chat_id,
            cutoff_timestamp=checkpoint.timestamp,
            checkpoint_id=checkpoint_id,
        )
        self.repo.update_chat_timestamp(chat, checkpoint.timestamp)
        self.repo.commit()

        history = self._assembler.assemble(chat_id)
        return RevertToCheckpointResponse(
            messages=history.messages,
            toolCalls=history.toolCalls,
            fileEdits=history.fileEdits,
            checkpoints=history.checkpoints,
            reasoningBlocks=history.reasoningBlocks,
        )

    def revert_file(self, chat_id: str, file_edit_id: str) -> RevertFileResponse:
        edit = self.repo.get_file_edit(file_edit_id)
        if edit is None or edit.chat_id != chat_id:
            raise ValueError(f"File edit not found: {file_edit_id}")

        self.repo.delete_file_edit(edit)
        self.repo.commit()

        remaining = [
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
        return RevertFileResponse(removedFileEditId=file_edit_id, fileEdits=remaining)
