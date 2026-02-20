"""Submit task tool — agent must call this to signal task completion."""

from __future__ import annotations

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.types import ToolExecutionResult


async def _handler(_payload: dict, context: ToolExecutionContext) -> ToolExecutionResult:
    if context.chat_id and context.chat_repo:
        todos = context.chat_repo.get_current_todos(context.chat_id)
        incomplete = [t for t in todos if (t.get("status") or "").lower() != "completed"]
        if incomplete:
            return ToolExecutionResult(
                output=(
                    "Todo list has incomplete items. Verify everything is done, use update_todo_list "
                    "to mark all items as completed, then call submit_task again."
                ),
                ok=False,
            )
    return ToolExecutionResult(output="Task submitted.", ok=True)


TOOL_PLUGIN = ToolPlugin(
    name="submit_task",
    description=(
        "Signal that you have completed all tasks. Call this once your work is done "
        "to end the agent loop. The loop continues until you call this tool."
    ),
    input_schema={"type": "object", "properties": {}},
    approval_policy="always",
    handler=_handler,
)
