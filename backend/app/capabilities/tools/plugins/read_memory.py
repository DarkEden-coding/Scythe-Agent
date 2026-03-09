from __future__ import annotations

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.types import ToolExecutionResult
from app.services.project_memory_service import ProjectMemoryService


def _resolve_project_id(context: ToolExecutionContext) -> str:
    if not context.chat_id or not context.chat_repo:
        raise ValueError("read_memory requires chat context")
    chat = context.chat_repo.get_chat(context.chat_id)
    if chat is None:
        raise ValueError(f"Chat not found: {context.chat_id}")
    return chat.project_id


async def _handler(payload: dict, context: ToolExecutionContext) -> ToolExecutionResult:
    repo = context.chat_repo
    if repo is None:
        return ToolExecutionResult(output="read_memory requires repository", file_edits=[], ok=False)
    try:
        project_id = _resolve_project_id(context)
        service = ProjectMemoryService(repo.db)
        titles = payload.get("titles")
        if titles is None:
            available = service.read_memory_titles(project_id=project_id)
            if not available:
                return ToolExecutionResult(output="No project memories found.", file_edits=[])
            rendered = "\n".join(f"- {title}" for title in available)
            return ToolExecutionResult(
                output=f"Available project memory titles:\n{rendered}",
                file_edits=[],
            )
        if not isinstance(titles, list) or any(not isinstance(title, str) for title in titles):
            return ToolExecutionResult(
                output="titles must be an array of strings",
                file_edits=[],
                ok=False,
            )
        memories = service.read_memories(project_id=project_id, titles=titles)
        if not memories:
            return ToolExecutionResult(output="No matching project memories found.", file_edits=[])
        rendered = "\n\n".join(
            f"# {memory.title}\n\n{memory.contentMarkdown}" for memory in memories
        )
        return ToolExecutionResult(output=rendered, file_edits=[])
    except ValueError as exc:
        return ToolExecutionResult(output=str(exc), file_edits=[], ok=False)


TOOL_PLUGIN = ToolPlugin(
    name="read_memory",
    description=(
        "Read one or more project memories by title. If no titles are provided, returns the available titles. "
        "Use this for durable user corrections/preferences only. Never treat memory as a place to store project data, code, plans, or retrieved context."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "titles": {
                "type": "array",
                "description": "Optional list of project memory titles to read. If omitted, available titles are returned.",
                "items": {"type": "string"},
            }
        },
    },
    approval_policy="always",
    handler=_handler,
)