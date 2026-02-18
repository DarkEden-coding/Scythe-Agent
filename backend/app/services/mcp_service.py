"""MCP server and tool management service."""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

from app.db.repositories.mcp_repo import MCPRepository
from app.mcp.client_manager import get_mcp_client_manager
from app.tools.mcp_bridge import build_mcp_tool_name
from app.tools.registry import get_tool_registry
from app.utils.ids import generate_id


class MCPService:
    """Handles MCP server CRUD and tool discovery."""

    def __init__(self, db: Session) -> None:
        self._repo = MCPRepository(db)

    def list_servers(self) -> list[dict]:
        """Return all servers with their tools for the settings UI."""
        servers = self._repo.list_all_servers()
        result = []
        for s in servers:
            tools = self._repo.list_cached_tools_for_server(s.id)
            result.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "transport": s.transport,
                    "configJson": s.config_json,
                    "enabled": bool(s.enabled),
                    "lastConnectedAt": s.last_connected_at,
                    "tools": [
                        {
                            "id": t.id,
                            "serverId": t.server_id,
                            "toolName": t.tool_name,
                            "description": t.description,
                            "enabled": bool(t.enabled),
                            "discoveredAt": t.discovered_at,
                        }
                        for t in tools
                    ],
                }
            )
        return result

    def create_server(self, *, name: str, transport: str, config_json: str) -> dict:
        """Create a new MCP server."""
        server_id = generate_id("mcp")
        # Validate JSON
        try:
            json.loads(config_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid config JSON: {e}") from e
        server = self._repo.create_server(
            id=server_id,
            name=name,
            transport=transport,
            config_json=config_json,
        )
        self._repo.commit()
        return {
            "id": server.id,
            "name": server.name,
            "transport": server.transport,
            "configJson": server.config_json,
            "enabled": bool(server.enabled),
            "lastConnectedAt": server.last_connected_at,
            "tools": [],
        }

    def update_server(
        self,
        server_id: str,
        *,
        name: str | None = None,
        transport: str | None = None,
        config_json: str | None = None,
    ) -> dict | None:
        """Update an MCP server. Returns None if not found."""
        server = self._repo.get_server(server_id)
        if not server:
            return None
        if config_json is not None:
            try:
                json.loads(config_json)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid config JSON: {e}") from e
        self._repo.update_server(server, name=name, transport=transport, config_json=config_json)
        self._repo.commit()
        tools = self._repo.list_cached_tools_for_server(server_id)
        return {
            "id": server.id,
            "name": server.name,
            "transport": server.transport,
            "configJson": server.config_json,
            "enabled": bool(server.enabled),
            "lastConnectedAt": server.last_connected_at,
            "tools": [
                {
                    "id": t.id,
                    "serverId": t.server_id,
                    "toolName": t.tool_name,
                    "description": t.description,
                    "enabled": bool(t.enabled),
                    "discoveredAt": t.discovered_at,
                }
                for t in tools
            ],
        }

    def delete_server(self, server_id: str) -> bool:
        """Delete an MCP server. Returns True if deleted."""
        server = self._repo.get_server(server_id)
        if not server:
            return False
        self._repo.delete_server(server_id)
        self._repo.commit()
        return True

    def set_server_enabled(self, server_id: str, enabled: bool) -> dict | None:
        """Toggle server enabled. Returns updated server or None."""
        server = self._repo.get_server(server_id)
        if not server:
            return None
        self._repo.set_server_enabled(server, enabled)
        self._repo.commit()
        tools = self._repo.list_cached_tools_for_server(server_id)
        return {
            "id": server.id,
            "name": server.name,
            "transport": server.transport,
            "configJson": server.config_json,
            "enabled": bool(server.enabled),
            "lastConnectedAt": server.last_connected_at,
            "tools": [
                {
                    "id": t.id,
                    "serverId": t.server_id,
                    "toolName": t.tool_name,
                    "description": t.description,
                    "enabled": bool(t.enabled),
                    "discoveredAt": t.discovered_at,
                }
                for t in tools
            ],
        }

    def set_tool_enabled(self, tool_id: str, enabled: bool) -> dict | None:
        """Toggle tool enabled. Returns updated tool or None."""
        tool = self._repo.get_cached_tool(tool_id)
        if not tool:
            return None
        self._repo.set_tool_enabled(tool, enabled)
        self._repo.commit()
        return {
            "id": tool.id,
            "serverId": tool.server_id,
            "toolName": tool.tool_name,
            "description": tool.description,
            "enabled": bool(tool.enabled),
            "discoveredAt": tool.discovered_at,
        }

    async def refresh_tools(self, server_id: str | None = None) -> dict:
        """Discover and cache tools, then refresh the tool registry."""
        manager = get_mcp_client_manager()
        discovered, errors = await manager.discover_and_cache_tools(
            self._repo.db, force_refresh=True
        )
        self._repo.commit()

        registry = get_tool_registry()
        registry.unregister_mcp_tools()
        registry.register_mcp_tools(
            [
                {
                    "server_id": t.server_id,
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in discovered
            ]
        )
        if errors:
            log.warning("MCP refresh had %d error(s): %s", len(errors), errors)
        return {
            "success": len(errors) == 0 or len(discovered) > 0,
            "discoveredCount": len(discovered),
            "errors": errors,
        }
