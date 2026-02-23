from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.project_repo import ProjectRepository
from app.schemas.chat import FileEditOut, RevertFileResponse, RevertToCheckpointResponse
from app.services.chat_history import ChatHistoryAssembler
from app.services.memory.observational.background import get_om_background_runner
from app.services.plan_file_store import PlanFileStore
from app.services.settings_service import SettingsService
from app.utils.mappers import map_file_action_for_ui


class RevertService:
    def __init__(self, db: Session):
        self.repo = ChatRepository(db)
        self._assembler = ChatHistoryAssembler(
            self.repo, ProjectRepository(db), SettingsService(db)
        )
        self._plan_store = PlanFileStore()

    @staticmethod
    def _is_after_cutoff(
        *,
        row_timestamp: str,
        cutoff_timestamp: str,
        row_checkpoint_id: str | None,
        target_checkpoint_id: str,
    ) -> bool:
        row_dt = datetime.fromisoformat(row_timestamp.replace("Z", "+00:00"))
        cutoff_dt = datetime.fromisoformat(cutoff_timestamp.replace("Z", "+00:00"))
        if row_dt > cutoff_dt:
            return True
        if row_dt == cutoff_dt and (
            row_checkpoint_id is None or row_checkpoint_id != target_checkpoint_id
        ):
            return True
        return False

    def revert_to_checkpoint(self, chat_id: str, checkpoint_id: str) -> RevertToCheckpointResponse:
        # Stop any in-flight observation work before mutating chat history.
        get_om_background_runner().cancel(chat_id)

        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        checkpoint = self.repo.get_checkpoint(checkpoint_id)
        if checkpoint is None or checkpoint.chat_id != chat_id:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        plans = self.repo.list_project_plans(chat_id)
        for plan in plans:
            revisions = self.repo.list_project_plan_revisions(plan.id)
            if not revisions:
                # Legacy fallback for plans created before revision ledger existed.
                created_after = self._is_after_cutoff(
                    row_timestamp=plan.created_at,
                    cutoff_timestamp=checkpoint.timestamp,
                    row_checkpoint_id=plan.checkpoint_id,
                    target_checkpoint_id=checkpoint_id,
                )
                updated_after = self._is_after_cutoff(
                    row_timestamp=plan.updated_at,
                    cutoff_timestamp=checkpoint.timestamp,
                    row_checkpoint_id=plan.checkpoint_id,
                    target_checkpoint_id=checkpoint_id,
                )
                if created_after or updated_after:
                    Path(plan.file_path).unlink(missing_ok=True)
                    self.repo.delete_project_plan(plan)
                continue

            latest = self.repo.get_latest_project_plan_revision_at_or_before(
                plan.id,
                checkpoint.timestamp,
                checkpoint_id,
            )
            if latest is None:
                Path(plan.file_path).unlink(missing_ok=True)
                self.repo.delete_project_plan(plan)
                continue

            restored_path, restored_sha = self._plan_store.write_plan(
                project_id=plan.project_id,
                plan_id=plan.id,
                content=latest.content_markdown,
            )
            self.repo.set_project_plan_content(
                plan,
                title=latest.title,
                checkpoint_id=latest.checkpoint_id,
                status=latest.status,
                file_path=str(restored_path),
                content_sha256=restored_sha,
                revision=latest.revision,
                last_editor=latest.last_editor,
                approved_action=latest.approved_action,
                implementation_chat_id=latest.implementation_chat_id,
                updated_at=latest.created_at,
            )
            self.repo.delete_project_plan_revisions_after_checkpoint(
                plan.id,
                checkpoint.timestamp,
                checkpoint_id,
            )

        tool_calls_to_remove = self.repo.list_tool_calls_after_checkpoint(
            chat_id, checkpoint.timestamp, checkpoint_id
        )
        for tc in tool_calls_to_remove:
            for artifact in self.repo.list_tool_artifacts_for_tool_call(tc.id):
                Path(artifact.file_path).unlink(missing_ok=True)

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
            subAgentRuns=history.subAgentRuns,
            fileEdits=history.fileEdits,
            checkpoints=history.checkpoints,
            reasoningBlocks=history.reasoningBlocks,
            todos=history.todos,
        )

    def revert_file(self, chat_id: str, file_edit_id: str) -> RevertFileResponse:
        # Avoid stale observation writes while reverting artifacts.
        get_om_background_runner().cancel(chat_id)

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
