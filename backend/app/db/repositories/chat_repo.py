import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, delete, or_
from sqlalchemy import select

from app.db.models.chat import Chat
from app.db.models.checkpoint import Checkpoint
from app.db.models.context_item import ContextItem
from app.db.models.file_edit import FileEdit
from app.db.models.file_snapshot import FileSnapshot
from app.db.models.memory_state import MemoryState
from app.db.models.message import Message
from app.db.models.observation import Observation
from app.db.models.reasoning_block import ReasoningBlock
from app.db.models.todo import Todo
from app.db.models.tool_artifact import ToolArtifact
from app.db.models.tool_call import ToolCall
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

    def _delete_todos_after_timestamp(
        self, chat_id: str, cutoff_ts: str, checkpoint_id: str
    ) -> None:
        """Delete legacy Todo rows created after a checkpoint revert cutoff."""
        cutoff_dt = _parse_ts_safe(cutoff_ts)
        if cutoff_dt is None:
            self.db.execute(delete(Todo).where(Todo.chat_id == chat_id))
            return

        todos = self.list_todos(chat_id)
        to_delete: list[str] = []
        for todo in todos:
            parsed = _parse_ts_safe(todo.timestamp)
            if parsed is None:
                to_delete.append(todo.id)
                continue
            if parsed > cutoff_dt:
                to_delete.append(todo.id)
                continue
            if parsed == cutoff_dt and (todo.checkpoint_id is None or todo.checkpoint_id != checkpoint_id):
                to_delete.append(todo.id)

        if to_delete:
            self.db.execute(delete(Todo).where(Todo.chat_id == chat_id, Todo.id.in_(to_delete)))

    def list_todos(self, chat_id: str) -> list[Todo]:
        """Return todos for a chat, ordered by sort_order then timestamp."""
        stmt = (
            select(Todo)
            .where(Todo.chat_id == chat_id)
            .order_by(Todo.sort_order.asc(), Todo.timestamp.asc())
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
            legacy = self.list_todos(chat_id)
            return [
                {
                    "id": t.id,
                    "content": t.content,
                    "status": t.status,
                    "sort_order": t.sort_order,
                    "timestamp": t.timestamp,
                }
                for t in legacy
            ]

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

    def replace_todos(
        self, chat_id: str, items: list[dict], *, timestamp: str
    ) -> None:
        """Replace all todos for a chat with the given items. Each item has content, status, sort_order."""
        normalized_ts = _normalize_ts(timestamp)
        self.db.execute(delete(Todo).where(Todo.chat_id == chat_id))
        for i, item in enumerate(items):
            self.db.add(
                Todo(
                    id=generate_id("todo"),
                    chat_id=chat_id,
                    content=str(item.get("content", "")),
                    status=str(item.get("status", "pending")),
                    sort_order=int(item.get("sort_order", i)),
                    timestamp=normalized_ts,
                )
            )

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

        raw_buffer = parsed_state.get("buffer") if isinstance(parsed_state.get("buffer"), dict) else {}
        raw_chunks = raw_buffer.get("chunks") if isinstance(raw_buffer.get("chunks"), list) else []
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
        self._delete_todos_after_timestamp(chat_id, cutoff, checkpoint_id)
        self._revert_observational_memory_after_timestamp(
            chat_id=chat_id,
            cutoff_ts=cutoff,
        )
