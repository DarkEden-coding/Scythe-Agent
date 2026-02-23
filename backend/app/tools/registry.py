from __future__ import annotations

from dataclasses import dataclass

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.loader import load_builtin_tool_plugins
from app.core.container import get_container
from app.tools.mcp_bridge import MCPBridgeTool
from app.tools.contracts import Tool, ToolResult


@dataclass
class ToolRegistryEntry:
    name: str
    source: str
    kind: str  # builtin | mcp
    approval_policy: str = "rules"


class _PluginToolAdapter:
    """Adapter to expose ToolPlugin through the legacy Tool protocol."""

    def __init__(self, plugin: ToolPlugin):
        self._plugin = plugin
        self.name = plugin.name
        self.description = plugin.description
        self.input_schema = plugin.input_schema

    async def run(
        self,
        payload: dict,
        *,
        project_root: str | None = None,
        chat_id: str | None = None,
        chat_repo=None,
        checkpoint_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> ToolResult:
        result = await self._plugin.handler(
            payload,
            ToolExecutionContext(
                project_root=project_root,
                chat_id=chat_id,
                chat_repo=chat_repo,
                checkpoint_id=checkpoint_id,
                tool_call_id=tool_call_id,
            ),
        )
        output = result.output_preview if result.output_preview is not None else result.output
        if result.error and not output:
            output = result.error
        return ToolResult(output=output, file_edits=result.file_edits, ok=result.ok)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._entries: dict[str, ToolRegistryEntry] = {}

    def register(
        self,
        tool: Tool,
        *,
        source: str = "builtin",
        kind: str = "builtin",
        approval_policy: str = "rules",
    ) -> None:
        self._tools[tool.name] = tool
        self._entries[tool.name] = ToolRegistryEntry(
            name=tool.name,
            source=source,
            kind=kind,
            approval_policy=approval_policy,
        )

    def get_tool(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())

    def list_entries(self) -> list[ToolRegistryEntry]:
        return [self._entries[name] for name in sorted(self._entries.keys())]

    def register_builtin_plugins(self) -> None:
        for plugin in load_builtin_tool_plugins():
            self.register(
                _PluginToolAdapter(plugin),
                source=plugin.source,
                kind="builtin",
                approval_policy=plugin.approval_policy,
            )

    def unregister_mcp_tools(self) -> None:
        """Remove all MCP tools from the registry (names start with mcp__)."""
        to_remove = [k for k in self._tools if k.startswith("mcp__")]
        for k in to_remove:
            self._tools.pop(k, None)
            self._entries.pop(k, None)

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
                self.register(
                    bridge,
                    source=f"mcp:{bridge.server_id}",
                    kind="mcp",
                    approval_policy="rules",
                )


def get_tool_registry() -> ToolRegistry:
    container = get_container()
    if container is None:
        raise RuntimeError("AppContainer is not initialized")
    return container.tool_registry


def reset_tool_registry() -> None:
    container = get_container()
    if container is None:
        return
    container.tool_registry = ToolRegistry()
    container.tool_registry.register_builtin_plugins()
