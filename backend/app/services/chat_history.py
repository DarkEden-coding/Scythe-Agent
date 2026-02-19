"""Assembles chat history for display; no EventBus or agent loop dependencies."""

from __future__ import annotations

from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.project_repo import ProjectRepository
from app.schemas.chat import (
    CheckpointOut,
    FileEditOut,
    GetChatHistoryResponse,
    MessageOut,
    ReasoningBlockOut,
    TodoOut,
    ToolCallOut,
)
from app.services.context_builder import build_context_items
from app.services.settings_service import SettingsService
from app.services.token_counter import TokenCounter
from app.utils.json_helpers import safe_parse_json
from app.utils.mappers import map_file_action_for_ui, map_role_for_ui


class ChatHistoryAssembler:
    """Assembles GetChatHistoryResponse from chat data."""

    def __init__(
        self,
        chat_repo: ChatRepository,
        project_repo: ProjectRepository,
        settings_service: SettingsService,
    ) -> None:
        self._chat_repo = chat_repo
        self._project_repo = project_repo
        self._settings_service = settings_service

    def assemble(self, chat_id: str) -> GetChatHistoryResponse:
        chat = self._chat_repo.get_chat(chat_id)
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
            for m in self._chat_repo.list_messages(chat_id)
        ]

        raw_tool_calls = self._chat_repo.list_tool_calls(chat_id)
        raw_file_edits = self._chat_repo.list_file_edits(chat_id)
        raw_reasoning_blocks = self._chat_repo.list_reasoning_blocks(chat_id)

        tool_calls = []
        for t in raw_tool_calls:
            spill = None
            if t.output_file_path:
                spill = (
                    f"The preceding tool output was truncated. "
                    f"Full output saved to: {t.output_file_path}. "
                    f"Use grep to locate relevant sections, then read_file with start/end (1-based) to read them."
                )
            tool_calls.append(
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
                    spillInstruction=spill,
                )
            )

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

        checkpoints = self._chat_repo.list_checkpoints(chat_id)
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

        raw_todos = self._chat_repo.list_todos(chat_id)
        todos = [
            TodoOut(
                id=t.id,
                content=t.content,
                status=t.status,
                sortOrder=t.sort_order,
                timestamp=t.timestamp,
            )
            for t in raw_todos
        ]

        settings = self._settings_service.get_settings()
        token_counter = TokenCounter(model=settings.model)
        context_items = build_context_items(
            chat_id=chat_id,
            chat_repo=self._chat_repo,
            project_repo=self._project_repo,
            token_counter=token_counter,
        )

        return GetChatHistoryResponse(
            chatId=chat_id,
            messages=messages,
            toolCalls=tool_calls,
            fileEdits=file_edits,
            checkpoints=checkpoints_out,
            reasoningBlocks=reasoning_blocks,
            contextItems=context_items,
            todos=todos,
            maxTokens=settings.contextLimit,
            model=settings.model,
        )
