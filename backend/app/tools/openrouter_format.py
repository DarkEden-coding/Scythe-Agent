"""Convert internal tool registry to OpenRouter/OpenAI function-calling format."""

from __future__ import annotations

from app.tools.contracts import Tool
from app.tools.registry import get_tool_registry


def tool_to_openrouter_spec(tool: Tool) -> dict:
    """
    Convert a Tool to OpenRouter/OpenAI function-calling format.

    Returns:
        Dict with "type": "function" and "function": {name, description, parameters}.
    """
    schema = dict(tool.input_schema) if tool.input_schema else {"type": "object"}
    if "type" not in schema:
        schema["type"] = "object"
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": schema,
        },
    }


def get_openrouter_tools() -> list[dict]:
    """Return all registered tools in OpenRouter format."""
    registry = get_tool_registry()
    tools: list[dict] = []
    for name in registry.list_tools():
        tool = registry.get_tool(name)
        if tool:
            tools.append(tool_to_openrouter_spec(tool))
    return tools
