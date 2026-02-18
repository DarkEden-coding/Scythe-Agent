from __future__ import annotations

from app.tools.builtin.edit_file import EditFileTool
from app.tools.builtin.execute_command import ExecuteCommandTool
from app.tools.builtin.grep import GrepTool
from app.tools.builtin.list_files import ListFilesTool
from app.tools.builtin.read_file import ReadFileTool
from app.tools.mcp_bridge import MCPBridgeTool
from app.tools.contracts import Tool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())

    def unregister_mcp_tools(self) -> None:
        """Remove all MCP tools from the registry (names start with mcp__)."""
        to_remove = [k for k in self._tools if k.startswith("mcp__")]
        for k in to_remove:
            del self._tools[k]

    def register_mcp_tools(self, tools: list[dict]) -> None:
        for tool in tools:
            schema_raw = tool.get("input_schema")
            schema = dict(schema_raw) if isinstance(schema_raw, dict) else {}
            bridge = MCPBridgeTool(
                server_id=str(tool.get("server_id", "")),
                tool_name=str(tool.get("name", "")),
                description=tool.get("description") if isinstance(tool.get("description"), str) else None,
                input_schema=schema,
            )
            if bridge.server_id and bridge.tool_name:
                self.register(bridge)


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        registry.register(ListFilesTool())
        registry.register(EditFileTool())
        registry.register(ExecuteCommandTool())
        registry.register(GrepTool())
        _registry = registry
    return _registry


def reset_tool_registry() -> None:
    global _registry
    _registry = None
