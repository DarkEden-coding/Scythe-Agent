from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MCPToolDescriptor:
    server_id: str
    name: str
    description: str | None
    input_schema: dict


@dataclass
class MCPToolCallResult:
    text_output: str


def parse_tools_list_response(payload: dict, *, server_id: str) -> list[MCPToolDescriptor]:
    tools_raw = payload.get("tools", [])
    if not isinstance(tools_raw, list):
        return []
    tools: list[MCPToolDescriptor] = []
    for item in tools_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        schema = item.get("inputSchema")
        if not isinstance(schema, dict):
            schema = item.get("input_schema") if isinstance(item.get("input_schema"), dict) else {}
        description = item.get("description")
        tools.append(
            MCPToolDescriptor(
                server_id=server_id,
                name=name,
                description=description if isinstance(description, str) else None,
                input_schema=schema,
            )
        )
    return tools


def parse_tool_call_result(payload: dict) -> MCPToolCallResult:
    content = payload.get("content", [])
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str):
                    return MCPToolCallResult(text_output=text)
    text_fallback = payload.get("text")
    if isinstance(text_fallback, str):
        return MCPToolCallResult(text_output=text_fallback)
    return MCPToolCallResult(text_output="")
