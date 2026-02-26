from __future__ import annotations

from app.mcp.client_manager import get_mcp_client_manager
from app.tools.contracts import ToolResult


def build_mcp_tool_name(*, server_id: str, tool_name: str) -> str:
    return f"mcp__{server_id}__{tool_name}"


class MCPBridgeTool:
    def __init__(
        self,
        *,
        server_id: str,
        tool_name: str,
        description: str | None,
        input_schema: dict,
    ):
        self.server_id = server_id
        self.tool_name = tool_name
        self.name = build_mcp_tool_name(server_id=server_id, tool_name=tool_name)
        self.description = description or f"MCP tool proxy for {tool_name}"
        self.input_schema = input_schema

    async def run(
        self,
        payload: dict,
        *,
        project_root: str | None = None,
        chat_id: str | None = None,
        chat_repo=None,
        checkpoint_id: str | None = None,
        tool_call_id: str | None = None,
        model_has_vision: bool = False,
    ) -> ToolResult:
        manager = get_mcp_client_manager()
        result = await manager.call_tool(self.server_id, self.tool_name, payload)
        return ToolResult(output=result.text_output, file_edits=[])
