"""User query tool — agent pauses to request more information from the user."""

from __future__ import annotations

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.types import ToolExecutionResult

USER_QUERY_SUCCESS_OUTPUT = "Awaiting user response."


async def _handler(_payload: dict, _context: ToolExecutionContext) -> ToolExecutionResult:
    return ToolExecutionResult(output=USER_QUERY_SUCCESS_OUTPUT, ok=True)


TOOL_PLUGIN = ToolPlugin(
    name="user_query",
    description=(
        "Pause the agent loop to request more information from the user. Use this when you "
        "need clarification, additional context, or decisions from the user before proceeding. "
        "Include your questions in your message text, then call this tool to end the turn until "
        "the user responds. The user's next message will resume the agent loop. No input required."
    ),
    input_schema={"type": "object", "properties": {}},
    approval_policy="always",
    handler=_handler,
)
