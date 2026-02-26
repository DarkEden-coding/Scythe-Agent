import json
from datetime import datetime
from typing import Any, cast

from sqlalchemy import and_, delete, or_
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.db.models.chat import Chat
from app.db.models.checkpoint import Checkpoint
from app.db.models.context_item import ContextItem
from app.db.models.file_edit import FileEdit
from app.db.models.file_snapshot import FileSnapshot
from app.db.models.memory_state import MemoryState
from app.db.models.message import Message
from app.db.models.message_attachment import MessageAttachment
from app.db.models.observation import Observation
from app.db.models.project_plan import ProjectPlan
from app.db.models.project_plan_revision import ProjectPlanRevision
from app.db.models.reasoning_block import ReasoningBlock
from app.db.models.tool_artifact import ToolArtifact
from app.db.models.tool_call import ToolCall
from app.db.models.sub_agent_run import SubAgentRun
from app.db.repositories.base_repo import BaseRepository
from app.utils.ids import generate_id
from app.utils.json_helpers import safe_parse_json
from app.utils.time import utc_now_iso
from app.utils.todos import normalize_todo_items


def _normalize_ts(iso_str: str) -> str:
    """Ensure ISO timestamp has consistent microsecond padding for string comparison."""
    dt = datetime.fromisoformat(iso_str)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def _parse_ts_safe(iso_str: str) -> datetime | None:
    """Parse ISO timestamp; return None if invalid."""
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class ChatRepository(BaseRepository):
    _UNSET = object()

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

    def get_project_plan(self, plan_id: str) -> ProjectPlan | None:
        return self.db.get(ProjectPlan, plan_id)

    def get_project_plan_revision(
        self, revision_id: str
    ) -> ProjectPlanRevision | None:
        return self.db.get(ProjectPlanRevision, revision_id)

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

    def list_sub_agent_runs(self, chat_id: str) -> list[SubAgentRun]:
        stmt = (
            select(SubAgentRun)
            .where(SubAgentRun.chat_id == chat_id)
            .order_by(SubAgentRun.timestamp.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_sub_agent_runs_for_tool_call(
        self, tool_call_id: str
    ) -> list[SubAgentRun]:
        stmt = (
            select(SubAgentRun)
            .where(SubAgentRun.tool_call_id == tool_call_id)
            .order_by(SubAgentRun.timestamp.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_sub_agent_run(self, sub_agent_id: str) -> SubAgentRun | None:
        return self.db.get(SubAgentRun, sub_agent_id)

    def create_sub_agent_run(
        self,
        *,
        sub_agent_id: str,
        chat_id: str,
        tool_call_id: str,
        task: str,
        model: str | None,
        status: str,
        timestamp: str,
        output_text: str | None = None,
        duration_ms: int | None = None,
    ) -> SubAgentRun:
        run = SubAgentRun(
            id=sub_agent_id,
            chat_id=chat_id,
            tool_call_id=tool_call_id,
            task=task,
            model=model,
            status=status,
            output_text=output_text,
            timestamp=timestamp,
            duration_ms=duration_ms,
        )
        self.db.add(run)
        return run

    def set_sub_agent_run_status(
        self,
        sub_agent_run: SubAgentRun,
        *,
        status: str,
        output_text: str | None = None,
        duration_ms: int | None = None,
    ) -> SubAgentRun:
        sub_agent_run.status = status
        if output_text is not None:
            sub_agent_run.output_text = output_text
        if duration_ms is not None:
            sub_agent_run.duration_ms = duration_ms
        return sub_agent_run

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

    def list_project_plans(self, chat_id: str) -> list[ProjectPlan]:
        stmt = (
            select(ProjectPlan)
            .where(ProjectPlan.chat_id == chat_id)
            .order_by(ProjectPlan.updated_at.asc())
        )
        try:
            return list(self.db.scalars(stmt).all())
        except OperationalError as exc:
            # Older local DBs may not have the project_plans table yet.
            if "no such table: project_plans" in str(exc).lower():
                return []
            raise

    def list_project_plans_touched_after_checkpoint(
        self, chat_id: str, cutoff_timestamp: str, checkpoint_id: str
    ) -> list[ProjectPlan]:
        cutoff = _normalize_ts(cutoff_timestamp)
        try:
            stmt = (
                select(ProjectPlan)
                .where(
                    ProjectPlan.chat_id == chat_id,
                    or_(
                        ProjectPlan.created_at > cutoff,
                        and_(
                            ProjectPlan.created_at == cutoff,
                            or_(
                                ProjectPlan.checkpoint_id.is_(None),
                                ProjectPlan.checkpoint_id != checkpoint_id,
                            ),
                        ),
                        ProjectPlan.updated_at > cutoff,
                        and_(
                            ProjectPlan.updated_at == cutoff,
                            or_(
                                ProjectPlan.checkpoint_id.is_(None),
                                ProjectPlan.checkpoint_id != checkpoint_id,
                            ),
                        ),
                    ),
                )
                .order_by(ProjectPlan.updated_at.asc())
            )
            return list(self.db.scalars(stmt).all())
        except OperationalError as exc:
            if "no such table: project_plans" in str(exc).lower():
                return []
            raise

    def list_project_plan_revisions(self, plan_id: str) -> list[ProjectPlanRevision]:
        try:
            stmt = (
                select(ProjectPlanRevision)
                .where(ProjectPlanRevision.plan_id == plan_id)
                .order_by(
                    ProjectPlanRevision.revision.asc(),
                    ProjectPlanRevision.created_at.asc(),
                )
            )
            return list(self.db.scalars(stmt).all())
        except OperationalError as exc:
            if "no such table: project_plan_revisions" in str(exc).lower():
                return []
            raise

    def get_latest_project_plan_revision_at_or_before(
        self, plan_id: str, cutoff_timestamp: str, checkpoint_id: str
    ) -> ProjectPlanRevision | None:
        cutoff = _normalize_ts(cutoff_timestamp)
        try:
            stmt = (
                select(ProjectPlanRevision)
                .where(
                    ProjectPlanRevision.plan_id == plan_id,
                    or_(
                        ProjectPlanRevision.created_at < cutoff,
                        and_(
                            ProjectPlanRevision.created_at == cutoff,
                            ProjectPlanRevision.checkpoint_id == checkpoint_id,
                        ),
                    ),
                )
                .order_by(
                    ProjectPlanRevision.revision.desc(),
                    ProjectPlanRevision.created_at.desc(),
                )
                .limit(1)
            )
            return self.db.scalars(stmt).first()
        except OperationalError as exc:
            if "no such table: project_plan_revisions" in str(exc).lower():
                return None
            raise

    def delete_project_plan_revisions_after_checkpoint(
        self, plan_id: str, cutoff_timestamp: str, checkpoint_id: str
    ) -> None:
        cutoff = _normalize_ts(cutoff_timestamp)
        try:
            self.db.execute(
                delete(ProjectPlanRevision).where(
                    ProjectPlanRevision.plan_id == plan_id,
                    or_(
                        ProjectPlanRevision.created_at > cutoff,
                        and_(
                            ProjectPlanRevision.created_at == cutoff,
                            or_(
                                ProjectPlanRevision.checkpoint_id.is_(None),
                                ProjectPlanRevision.checkpoint_id != checkpoint_id,
                            ),
                        ),
                    ),
                )
            )
        except OperationalError as exc:
            if "no such table: project_plan_revisions" in str(exc).lower():
                return
            raise

    def list_context_items(self, chat_id: str) -> list[ContextItem]:
        stmt = (
            select(ContextItem)
            .where(ContextItem.chat_id == chat_id)
            .order_by(ContextItem.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_current_todos(self, chat_id: str) -> list[dict]:
        """Return the active todo state derived from the latest successful update_todo_list call."""
        latest_stmt = (
            select(ToolCall)
            .where(
                ToolCall.chat_id == chat_id,
                ToolCall.name == "update_todo_list",
                ToolCall.status == "completed",
            )
            .order_by(ToolCall.timestamp.desc())
        )
        latest = self.db.scalars(latest_stmt).first()
        if latest is None:
            return []

        payload = safe_parse_json(latest.input_json)
        items = payload.get("todos") if isinstance(payload, dict) else []
        normalized = normalize_todo_items(items)
        return [
            {
                "id": f"todo-{latest.id}-{idx}",
                "content": item["content"],
                "status": item["status"],
                "sort_order": item["sort_order"],
                "timestamp": latest.timestamp,
            }
            for idx, item in enumerate(normalized)
        ]

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

    def create_message_attachment(
        self,
        *,
        attachment_id: str,
        message_id: str,
        content_base64: str,
        mime_type: str,
        sort_order: int = 0,
    ) -> MessageAttachment:
        attachment = MessageAttachment(
            id=attachment_id,
            message_id=message_id,
            content_base64=content_base64,
            mime_type=mime_type,
            sort_order=sort_order,
        )
        self.db.add(attachment)
        return attachment

    def update_message_image_summarization(
        self, message_id: str, summary: str, model: str
    ) -> None:
        """Store image summarization from vision preprocessor on a user message."""
        msg = self.db.get(Message, message_id)
        if msg:
            msg.image_summarization = summary
            msg.image_summarization_model = model

    def list_attachments_for_message(self, message_id: str) -> list[MessageAttachment]:
        stmt = (
            select(MessageAttachment)
            .where(MessageAttachment.message_id == message_id)
            .order_by(MessageAttachment.sort_order.asc())
        )
        return list(self.db.scalars(stmt).all())

    def delete_attachments_for_message(self, message_id: str) -> None:
        self.db.execute(delete(MessageAttachment).where(MessageAttachment.message_id == message_id))

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

    def create_project_plan(
        self,
        *,
        plan_id: str,
        chat_id: str,
        project_id: str,
        checkpoint_id: str | None,
        title: str,
        status: str,
        file_path: str,
        revision: int,
        content_sha256: str,
        last_editor: str,
        approved_action: str | None,
        implementation_chat_id: str | None,
        created_at: str,
        updated_at: str,
    ) -> ProjectPlan:
        plan = ProjectPlan(
            id=plan_id,
            chat_id=chat_id,
            project_id=project_id,
            checkpoint_id=checkpoint_id,
            title=title,
            status=status,
            file_path=file_path,
            revision=revision,
            content_sha256=content_sha256,
            last_editor=last_editor,
            approved_action=approved_action,
            implementation_chat_id=implementation_chat_id,
            created_at=created_at,
            updated_at=updated_at,
        )
        self.db.add(plan)
        return plan

    def create_project_plan_revision(
        self,
        *,
        revision_id: str,
        plan_id: str,
        chat_id: str,
        project_id: str,
        checkpoint_id: str | None,
        revision: int,
        title: str,
        status: str,
        file_path: str,
        content_markdown: str,
        content_sha256: str,
        last_editor: str,
        approved_action: str | None,
        implementation_chat_id: str | None,
        created_at: str,
    ) -> ProjectPlanRevision:
        row = ProjectPlanRevision(
            id=revision_id,
            plan_id=plan_id,
            chat_id=chat_id,
            project_id=project_id,
            checkpoint_id=checkpoint_id,
            revision=revision,
            title=title,
            status=status,
            file_path=file_path,
            content_markdown=content_markdown,
            content_sha256=content_sha256,
            last_editor=last_editor,
            approved_action=approved_action,
            implementation_chat_id=implementation_chat_id,
            created_at=created_at,
        )
        self.db.add(row)
        return row

    def set_project_plan_content(
        self,
        plan: ProjectPlan,
        *,
        title: str | None = None,
        checkpoint_id: str | None | object = _UNSET,
        status: str | None = None,
        file_path: str | None = None,
        content_sha256: str | None = None,
        revision: int | None = None,
        last_editor: str | None = None,
        approved_action: str | None | object = _UNSET,
        implementation_chat_id: str | None | object = _UNSET,
        updated_at: str | None = None,
    ) -> ProjectPlan:
        if title is not None:
            plan.title = title
        if checkpoint_id is not self._UNSET:
            plan.checkpoint_id = cast(str | None, checkpoint_id)
        if status is not None:
            plan.status = status
        if file_path is not None:
            plan.file_path = file_path
        if content_sha256 is not None:
            plan.content_sha256 = content_sha256
        if revision is not None:
            plan.revision = revision
        if last_editor is not None:
            plan.last_editor = last_editor
        if approved_action is not self._UNSET:
            plan.approved_action = cast(str | None, approved_action)
        if implementation_chat_id is not self._UNSET:
            plan.implementation_chat_id = cast(str | None, implementation_chat_id)
        if updated_at is not None:
            plan.updated_at = updated_at
        return plan

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

    def delete_project_plan(self, project_plan: ProjectPlan) -> None:
        self.db.delete(project_plan)

    def create_tool_artifact(
        self,
        *,
        artifact_id: str,
        tool_call_id: str,
        chat_id: str,
        project_id: str,
        artifact_type: str,
        file_path: str,
        line_count: int | None,
        preview_lines: int | None,
        created_at: str,
    ) -> ToolArtifact:
        artifact = ToolArtifact(
            id=artifact_id,
            tool_call_id=tool_call_id,
            chat_id=chat_id,
            project_id=project_id,
            artifact_type=artifact_type,
            file_path=file_path,
            line_count=line_count,
            preview_lines=preview_lines,
            created_at=created_at,
        )
        self.db.add(artifact)
        return artifact

    def list_tool_artifacts_for_tool_call(self, tool_call_id: str) -> list[ToolArtifact]:
        stmt = (
            select(ToolArtifact)
            .where(ToolArtifact.tool_call_id == tool_call_id)
            .order_by(ToolArtifact.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_tool_artifacts_for_chat(self, chat_id: str) -> list[ToolArtifact]:
        stmt = (
            select(ToolArtifact)
            .where(ToolArtifact.chat_id == chat_id)
            .order_by(ToolArtifact.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def set_memory_state(
        self,
        *,
        chat_id: str,
        strategy: str,
        state_json: str,
        updated_at: str,
    ) -> MemoryState:
        stmt = select(MemoryState).where(MemoryState.chat_id == chat_id)
        existing = self.db.scalars(stmt).first()
        if existing is None:
            existing = MemoryState(
                id=generate_id("mem"),
                chat_id=chat_id,
                strategy=strategy,
                state_json=state_json,
                updated_at=updated_at,
            )
            self.db.add(existing)
        else:
            existing.strategy = strategy
            existing.state_json = state_json
            existing.updated_at = updated_at
        return existing

    def get_memory_state(self, chat_id: str) -> MemoryState | None:
        stmt = select(MemoryState).where(MemoryState.chat_id == chat_id)
        return self.db.scalars(stmt).first()

    def get_latest_observation(self, chat_id: str) -> Observation | None:
        """Return the highest-generation, most-recent observation for a chat."""
        stmt = (
            select(Observation)
            .where(Observation.chat_id == chat_id)
            .order_by(Observation.generation.desc(), Observation.timestamp.desc())
        )
        return self.db.scalars(stmt).first()

    def list_observations(self, chat_id: str) -> list[Observation]:
        stmt = (
            select(Observation)
            .where(Observation.chat_id == chat_id)
            .order_by(Observation.generation.desc(), Observation.timestamp.desc())
        )
        return list(self.db.scalars(stmt).all())

    def create_observation(
        self,
        *,
        observation_id: str,
        chat_id: str,
        generation: int,
        content: str,
        token_count: int,
        observed_up_to_message_id: str | None,
        current_task: str | None,
        suggested_response: str | None,
        timestamp: str,
        trigger_token_count: int | None = None,
    ) -> Observation:
        obs = Observation(
            id=observation_id,
            chat_id=chat_id,
            generation=generation,
            content=content,
            token_count=token_count,
            trigger_token_count=(
                trigger_token_count
                if isinstance(trigger_token_count, int) and trigger_token_count > 0
                else token_count
            ),
            observed_up_to_message_id=observed_up_to_message_id,
            current_task=current_task,
            suggested_response=suggested_response,
            timestamp=timestamp,
        )
        self.db.add(obs)
        return obs

    def delete_observation(self, obs: Observation) -> None:
        """Delete a specific observation by ID (direct SQL to avoid ORM tracking issues)."""
        self.db.execute(
            delete(Observation).where(Observation.id == obs.id)
        )

    def delete_observations_before_generation(
        self, chat_id: str, generation: int
    ) -> None:
        """Delete all observations with generation < given value (cleanup after reflection)."""
        self.db.execute(
            delete(Observation).where(
                Observation.chat_id == chat_id,
                Observation.generation < generation,
            )
        )

    def delete_observations_for_chat(self, chat_id: str) -> None:
        """Delete all observations for a chat (for revert/delete support)."""
        self.db.execute(
            delete(Observation).where(Observation.chat_id == chat_id)
        )
        self.db.execute(
            delete(MemoryState).where(MemoryState.chat_id == chat_id)
        )

    def _revert_observational_memory_after_timestamp(
        self,
        *,
        chat_id: str,
        cutoff_ts: str,
    ) -> None:
        """Trim observational memory to data that is still valid at the checkpoint cutoff."""
        cutoff_dt = _parse_ts_safe(cutoff_ts)
        if cutoff_dt is None:
            self.db.execute(delete(Observation).where(Observation.chat_id == chat_id))
            self.db.execute(delete(MemoryState).where(MemoryState.chat_id == chat_id))
            return

        valid_message_ids = {m.id for m in self.list_messages(chat_id)}

        observations = self.list_observations(chat_id)
        observation_ids_to_delete: list[str] = []
        valid_observations: list[Observation] = []
        for obs in observations:
            obs_dt = _parse_ts_safe(obs.timestamp)
            if obs_dt is None or obs_dt > cutoff_dt:
                observation_ids_to_delete.append(obs.id)
                continue
            if obs.observed_up_to_message_id and obs.observed_up_to_message_id not in valid_message_ids:
                observation_ids_to_delete.append(obs.id)
                continue
            valid_observations.append(obs)

        if observation_ids_to_delete:
            self.db.execute(
                delete(Observation).where(
                    Observation.chat_id == chat_id,
                    Observation.id.in_(observation_ids_to_delete),
                )
            )

        latest_observation = valid_observations[0] if valid_observations else None
        state_row = self.get_memory_state(chat_id)
        if state_row is None or state_row.strategy != "observational":
            return

        parsed_state: dict[str, Any] = {}
        if isinstance(state_row.state_json, str):
            try:
                raw_state = json.loads(state_row.state_json)
                if isinstance(raw_state, dict):
                    parsed_state = raw_state
            except Exception:
                parsed_state = {}

        # Safely get 'buffer' and ensure it's a dictionary
        buffer_data = parsed_state.get("buffer")
        raw_buffer: dict[str, Any] = buffer_data if isinstance(buffer_data, dict) else {}

        # Safely get 'chunks' from raw_buffer and ensure it's a list
        chunks_data = raw_buffer.get("chunks")
        raw_chunks: list[dict[str, Any]] = chunks_data if isinstance(chunks_data, list) else []
        valid_chunks: list[dict[str, Any]] = []
        for raw_chunk in raw_chunks:
            if not isinstance(raw_chunk, dict):
                continue
            content = raw_chunk.get("content")
            if not isinstance(content, str) or not content.strip():
                continue

            observed_up_to_message_id = raw_chunk.get("observedUpToMessageId")
            if observed_up_to_message_id is not None:
                if not isinstance(observed_up_to_message_id, str):
                    continue
                if observed_up_to_message_id not in valid_message_ids:
                    continue

            observed_up_to_timestamp = raw_chunk.get("observedUpToTimestamp")
            if observed_up_to_timestamp is not None:
                if not isinstance(observed_up_to_timestamp, str):
                    continue
                chunk_dt = _parse_ts_safe(observed_up_to_timestamp)
                if chunk_dt is None or chunk_dt > cutoff_dt:
                    continue

            token_count = raw_chunk.get("tokenCount")
            if isinstance(token_count, int) and token_count > 0:
                normalized_token_count = token_count
            else:
                try:
                    import tiktoken
                    _enc = tiktoken.get_encoding("cl100k_base")
                    normalized_token_count = len(_enc.encode(content.strip())) or 1
                except Exception:
                    normalized_token_count = max(1, len(content.strip()) // 4)

            current_task = raw_chunk.get("currentTask")
            suggested_response = raw_chunk.get("suggestedResponse")
            valid_chunks.append(
                {
                    "content": content.strip(),
                    "tokenCount": normalized_token_count,
                    "observedUpToMessageId": (
                        observed_up_to_message_id if isinstance(observed_up_to_message_id, str) else None
                    ),
                    "observedUpToTimestamp": (
                        observed_up_to_timestamp if isinstance(observed_up_to_timestamp, str) else None
                    ),
                    "currentTask": (
                        current_task.strip()
                        if isinstance(current_task, str) and current_task.strip()
                        else None
                    ),
                    "suggestedResponse": (
                        suggested_response.strip()
                        if isinstance(suggested_response, str) and suggested_response.strip()
                        else None
                    ),
                }
            )

        if latest_observation is None and not valid_chunks:
            self.db.execute(delete(MemoryState).where(MemoryState.chat_id == chat_id))
            return

        next_state: dict[str, Any] = dict(parsed_state)
        if latest_observation is None:
            for key in (
                "generation",
                "tokenCount",
                "triggerTokenCount",
                "observedUpToMessageId",
                "currentTask",
                "suggestedResponse",
                "timestamp",
                "content",
            ):
                next_state.pop(key, None)
        else:
            next_state["generation"] = latest_observation.generation
            next_state["tokenCount"] = latest_observation.token_count
            next_state["triggerTokenCount"] = (
                latest_observation.trigger_token_count
                if isinstance(latest_observation.trigger_token_count, int)
                and latest_observation.trigger_token_count > 0
                else latest_observation.token_count
            )
            next_state["observedUpToMessageId"] = latest_observation.observed_up_to_message_id
            next_state["currentTask"] = latest_observation.current_task
            next_state["suggestedResponse"] = latest_observation.suggested_response
            next_state["timestamp"] = latest_observation.timestamp
            next_state["content"] = latest_observation.content

        # Recalculate buffer token count from surviving chunks so the
        # observation trigger threshold reflects the actual post-revert state.
        normalized_buffer_tokens = sum(c.get("tokenCount", 0) for c in valid_chunks)
        if normalized_buffer_tokens <= 0:
            normalized_buffer_tokens = 500
        buffer_up_to_message_id: str | None = None
        buffer_up_to_timestamp: str | None = None
        if latest_observation is not None:
            buffer_up_to_message_id = latest_observation.observed_up_to_message_id
            buffer_up_to_timestamp = latest_observation.timestamp
        elif valid_chunks:
            last_chunk = valid_chunks[-1]
            raw_up_to_message = last_chunk.get("observedUpToMessageId")
            raw_up_to_timestamp = last_chunk.get("observedUpToTimestamp")
            buffer_up_to_message_id = raw_up_to_message if isinstance(raw_up_to_message, str) else None
            buffer_up_to_timestamp = raw_up_to_timestamp if isinstance(raw_up_to_timestamp, str) else None

        next_state["buffer"] = {
            "tokens": normalized_buffer_tokens,
            "lastBoundary": 0,
            "upToMessageId": buffer_up_to_message_id,
            "upToTimestamp": buffer_up_to_timestamp,
            "chunks": valid_chunks,
        }

        self.set_memory_state(
            chat_id=chat_id,
            strategy="observational",
            state_json=json.dumps(next_state),
            updated_at=utc_now_iso(),
        )

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
        tool_call_ids_to_remove = [
            t.id
            for t in self.list_tool_calls_after_checkpoint(chat_id, cutoff, checkpoint_id)
        ]
        if tool_call_ids_to_remove:
            self.db.execute(
                delete(SubAgentRun).where(
                    SubAgentRun.chat_id == chat_id,
                    SubAgentRun.tool_call_id.in_(tool_call_ids_to_remove),
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
        self._revert_observational_memory_after_timestamp(
            chat_id=chat_id,
            cutoff_ts=cutoff,
        )
