"""Update todo list tool for agent task tracking."""

from __future__ import annotations

from app.tools.contracts import ToolResult
from app.utils.time import utc_now_iso


class UpdateTodoListTool:
    """Replace the chat's todo list with the provided items."""

    name = "update_todo_list"
    description = (
        "Update your current task/reminder list. Use this for multi-step tasks: "
        "create items with status 'pending', mark 'in_progress' when working on them, "
        "and 'completed' when done. Call whenever you add, edit, check off, or complete items. "
        "Pass the full list each time (replaces existing)."
    )
    input_schema = {
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
    }

    async def run(
        self,
        payload: dict,
        *,
        project_root: str | None = None,
        chat_id: str | None = None,
        chat_repo=None,
    ) -> ToolResult:
        if not chat_id:
            return ToolResult(
                output="update_todo_list requires chat context",
                file_edits=[],
                ok=False,
            )
        if not chat_repo:
            return ToolResult(
                output="update_todo_list requires repository",
                file_edits=[],
                ok=False,
            )
        items = payload.get("todos") or []
        if not isinstance(items, list):
            return ToolResult(
                output="todos must be an array",
                file_edits=[],
                ok=False,
            )
        normalized = []
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            status = str(item.get("status", "pending")).lower()
            if status not in ("pending", "in_progress", "completed"):
                status = "pending"
            normalized.append({
                "content": content,
                "status": status,
                "sort_order": int(item.get("sort_order", i)),
            })
        timestamp = utc_now_iso()
        chat_repo.replace_todos(chat_id, normalized, timestamp=timestamp)
        chat_repo.commit()
        return ToolResult(
            output=f"Todo list updated with {len(normalized)} item(s).",
            file_edits=[],
            ok=True,
        )
