"""Update todo list tool for agent task tracking."""

from __future__ import annotations

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.types import ToolExecutionResult
from app.utils.todos import normalize_todo_items


async def _handler(payload: dict, context: ToolExecutionContext) -> ToolExecutionResult:
    if not context.chat_id:
        return ToolExecutionResult(
            output="update_todo_list requires chat context",
            file_edits=[],
            ok=False,
        )
    if not context.chat_repo:
        return ToolExecutionResult(
            output="update_todo_list requires repository",
            file_edits=[],
            ok=False,
        )
    items = payload.get("todos") or []
    if not isinstance(items, list):
        return ToolExecutionResult(
            output="todos must be an array",
            file_edits=[],
            ok=False,
        )
    normalized = normalize_todo_items(items)
    return ToolExecutionResult(
        output=f"Todo list updated with {len(normalized)} item(s).",
        file_edits=[],
        ok=True,
    )


TOOL_PLUGIN = ToolPlugin(
    name="update_todo_list",
    description=(
        "Update your current task/reminder list. Use this for multi-step tasks: "
        "create items with status 'pending', mark 'in_progress' when working on them, "
        "and 'completed' when done. Call whenever you add, edit, check off, or complete items. "
        "Pass the full list each time (replaces existing)."
    ),
    input_schema={
        "type": "object",
        "required": ["todos"],
        "properties": {
            "todos": {
                "type": "array",
                "description": "Full list of todos. Each item has content and status.",
                "items": {
                    "type": "object",
                    "required": ["content"],
                    "properties": {
                        "content": {"type": "string", "description": "Task description"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "default": "pending",
                        },
                        "sort_order": {
                            "type": "integer",
                            "description": "Display order (0-based)",
                            "default": 0,
                        },
                    },
                },
            },
        },
    },
    approval_policy="always",
    handler=_handler,
)
