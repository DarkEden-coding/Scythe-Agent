from __future__ import annotations

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.types import ToolExecutionResult
from app.services.project_memory_service import ProjectMemoryService


def _resolve_project_id(context: ToolExecutionContext) -> str:
    if not context.chat_id or not context.chat_repo:
        raise ValueError("write_memory requires chat context")
    chat = context.chat_repo.get_chat(context.chat_id)
    if chat is None:
        raise ValueError(f"Chat not found: {context.chat_id}")
    return chat.project_id


async def _handler(payload: dict, context: ToolExecutionContext) -> ToolExecutionResult:
    title = payload.get("title")
    content_markdown = payload.get("content_markdown")
    if not isinstance(title, str) or not isinstance(content_markdown, str):
        return ToolExecutionResult(
            output="title and content_markdown must be strings",
            file_edits=[],
            ok=False,
        )
    repo = context.chat_repo
    if repo is None:
        return ToolExecutionResult(output="write_memory requires repository", file_edits=[], ok=False)
    try:
        project_id = _resolve_project_id(context)
        service = ProjectMemoryService(repo.db)
        memory = service.upsert_project_memory(
            project_id=project_id,
            title=title,
            content_markdown=content_markdown,
        ).memory
        return ToolExecutionResult(
            output=(
                f"Saved project memory '{memory.title}'. "
                "Only store durable user corrections/preferences; never store project data, code, plans, or retrieved context."
            ),
            file_edits=[],
        )
    except ValueError as exc:
        return ToolExecutionResult(output=str(exc), file_edits=[], ok=False)


TOOL_PLUGIN = ToolPlugin(
    name="write_memory",
    description=(
        "Create or replace a minimal project memory by title. Use only for durable user corrections/preferences that should persist across conversations. "
        "Never store project data, code, plans, business context, or retrieved context. Keep entries minimal."
    ),
    input_schema={
        "type": "object",
        "required": ["title", "content_markdown"],
        "properties": {
            "title": {"type": "string", "description": "Short memory title"},
            "content_markdown": {
                "type": "string",
                "description": "Minimal markdown note containing a durable user correction or preference",
            },
        },
    },
    approval_policy="always",
    handler=_handler,
)