from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.project_repo import ProjectRepository
from app.schemas.chat import FileEditOut, RevertFileResponse, RevertToCheckpointResponse
from app.services.chat_history import ChatHistoryAssembler
from app.services.settings_service import SettingsService
from app.utils.mappers import map_file_action_for_ui


class RevertService:
    def __init__(self, db: Session):
        self.repo = ChatRepository(db)
        self._assembler = ChatHistoryAssembler(
            self.repo, ProjectRepository(db), SettingsService(db)
        )

    def revert_to_checkpoint(self, chat_id: str, checkpoint_id: str) -> RevertToCheckpointResponse:
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        checkpoint = self.repo.get_checkpoint(checkpoint_id)
        if checkpoint is None or checkpoint.chat_id != chat_id:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        tool_calls_to_remove = self.repo.list_tool_calls_after_checkpoint(
            chat_id, checkpoint.timestamp, checkpoint_id
        )
        for tc in tool_calls_to_remove:
            if tc.output_file_path:
                spill_path = Path(tc.output_file_path)
                spill_path.unlink(missing_ok=True)

        # Restore files from snapshots (reverse chronological so last changes are undone first)
        snapshots = self.repo.list_file_snapshots_after_checkpoint(
            chat_id, checkpoint.timestamp, checkpoint_id
        )
        for snapshot in snapshots:
            path = Path(snapshot.file_path)
            if snapshot.content is None:
                # File was created by the agent — delete it
                path.unlink(missing_ok=True)
            else:
                # File was modified — restore original content
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(snapshot.content, encoding="utf-8")

        self.repo.delete_file_snapshots_after_checkpoint(
            chat_id, checkpoint.timestamp, checkpoint_id
        )
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
            todos=history.todos,
        )

    def revert_file(self, chat_id: str, file_edit_id: str) -> RevertFileResponse:
        edit = self.repo.get_file_edit(file_edit_id)
        if edit is None or edit.chat_id != chat_id:
            raise ValueError(f"File edit not found: {file_edit_id}")

        # Restore file from snapshot if available
        snapshot = self.repo.get_file_snapshot_by_edit(file_edit_id)
        if snapshot is not None:
            path = Path(snapshot.file_path)
            if snapshot.content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(snapshot.content, encoding="utf-8")
            self.repo.delete_file_snapshot(snapshot)

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
