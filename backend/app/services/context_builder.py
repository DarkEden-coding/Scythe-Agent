"""Builds context items with token counts for display."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.initial_information.project_overview import add_project_overview_3_levels
from app.schemas.chat import ContextItemOut
from app.services.token_counter import TokenCounter

if TYPE_CHECKING:
    from app.db.repositories.chat_repo import ChatRepository
    from app.db.repositories.project_repo import ProjectRepository


def _truncate_label(s: str, max_len: int = 48) -> str:
    s = s.strip().replace("\n", " ")
    return (s[: max_len - 3] + "...") if len(s) > max_len else s


def build_context_items(
    chat_id: str,
    chat_repo: ChatRepository,
    project_repo: ProjectRepository,
    token_counter: TokenCounter,
) -> list[ContextItemOut]:
    """
    Derive context items from chat data and count tokens per item.

    Categories: file (project structure), conversation (messages), tool_output,
    reasoning (reasoning blocks). Uses DB-stored context_items when present and
    non-empty; otherwise builds from messages, tool calls, reasoning, project overview.
    """
    stored = chat_repo.list_context_items(chat_id)
    if stored:
        return [
            ContextItemOut(id=c.id, type=c.type, name=c.label, tokens=c.tokens, full_name=None)
            for c in stored
        ]

    items: list[ContextItemOut] = []
    chat = chat_repo.get_chat(chat_id)
    project_path = None
    if chat:
        project = project_repo.get_project(chat.project_id)
        if project:
            project_path = project.path

    if project_path:
        base_messages = [{"role": "user", "content": ""}]
        enhanced = add_project_overview_3_levels(base_messages, project_path=project_path)
        for m in enhanced:
            if m.get("role") == "system":
                content = m.get("content", "")
                if content:
                    tokens = token_counter.count(content)
                    items.append(
                        ContextItemOut(
                            id=f"ctx-file-{chat_id[:8]}",
                            type="file",
                            name="Project structure",
                            tokens=tokens,
                            full_name=project_path,
                        )
                    )
                break

    messages = chat_repo.list_messages(chat_id)
    for i, m in enumerate(messages):
        content = m.content or ""
        label = f"{m.role}: {_truncate_label(content)}"
        tokens = token_counter.count(content)
        items.append(
            ContextItemOut(
                id=m.id,
                type="conversation",
                name=label,
                tokens=tokens,
                full_name=f"{m.role}: {content}" if len(content) > 48 else None,
            )
        )

    tool_calls = chat_repo.list_tool_calls(chat_id)
    for tc in tool_calls:
        payload = f"{tc.name}({tc.input_json})"
        if tc.output_text:
            payload += f" -> {tc.output_text}"
        tokens = token_counter.count(payload)
        items.append(
            ContextItemOut(
                id=tc.id,
                type="tool_output",
                name=f"{tc.name}: {_truncate_label(tc.input_json)}",
                tokens=tokens,
                full_name=f"{tc.name}({tc.input_json})",
            )
        )

    reasoning_blocks = chat_repo.list_reasoning_blocks(chat_id)
    for rb in reasoning_blocks:
        tokens = token_counter.count(rb.content or "")
        content = rb.content or ""
        items.append(
            ContextItemOut(
                id=rb.id,
                type="conversation",
                name=f"Reasoning: {_truncate_label(content)}",
                tokens=tokens,
                full_name=f"Reasoning: {content}" if len(content) > 48 else None,
            )
        )

    return items
