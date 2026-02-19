from __future__ import annotations

from sqlalchemy import select

from app.db.models.mcp_server import MCPServer
from app.db.models.mcp_tool_cache import MCPToolCache
from app.db.repositories.base_repo import BaseRepository


class MCPRepository(BaseRepository):
    def list_enabled_servers(self) -> list[MCPServer]:
        stmt = (
            select(MCPServer)
            .where(MCPServer.enabled == 1)
            .order_by(MCPServer.name.asc(), MCPServer.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_all_servers(self) -> list[MCPServer]:
        stmt = select(MCPServer).order_by(MCPServer.name.asc(), MCPServer.id.asc())
        return list(self.db.scalars(stmt).all())

    def get_server(self, server_id: str) -> MCPServer | None:
        return self.db.get(MCPServer, server_id)

    def create_server(
        self,
        *,
        id: str,
        name: str,
        transport: str,
        config_json: str,
    ) -> MCPServer:
        server = MCPServer(
            id=id,
            name=name,
            transport=transport,
            config_json=config_json,
            enabled=1,
            last_connected_at=None,
        )
        self.db.add(server)
        return server

    def update_server(
        self,
        server: MCPServer,
        *,
        name: str | None = None,
        transport: str | None = None,
        config_json: str | None = None,
    ) -> MCPServer:
        if name is not None:
            server.name = name
        if transport is not None:
            server.transport = transport
        if config_json is not None:
            server.config_json = config_json
        return server

    def delete_server(self, server_id: str) -> None:
        server = self.db.get(MCPServer, server_id)
        if server:
            self.db.delete(server)

    def set_server_enabled(self, server: MCPServer, enabled: bool) -> None:
        server.enabled = 1 if enabled else 0

    def list_cached_tools(self) -> list[MCPToolCache]:
        stmt = select(MCPToolCache).order_by(MCPToolCache.tool_name.asc(), MCPToolCache.id.asc())
        return list(self.db.scalars(stmt).all())

    def list_cached_tools_for_server(
        self, server_id: str, *, enabled_only: bool = False
    ) -> list[MCPToolCache]:
        stmt = (
            select(MCPToolCache)
            .where(MCPToolCache.server_id == server_id)
            .order_by(MCPToolCache.tool_name.asc(), MCPToolCache.id.asc())
        )
        if enabled_only:
            stmt = stmt.where(MCPToolCache.enabled == 1)
        return list(self.db.scalars(stmt).all())

    def get_cached_tool(self, tool_id: str) -> MCPToolCache | None:
        return self.db.get(MCPToolCache, tool_id)

    def replace_server_tools(self, *, server_id: str, tools: list[MCPToolCache]) -> None:
        existing = {t.tool_name: t for t in self.list_cached_tools_for_server(server_id)}
        discovered_names = {t.tool_name for t in tools}
        for name in list(existing.keys()):
            if name not in discovered_names:
                self.db.delete(existing[name])
        for tool in tools:
            prev = existing.get(tool.tool_name)
            if prev:
                prev.schema_json = tool.schema_json
                prev.description = tool.description
                prev.discovered_at = tool.discovered_at
            else:
                self.db.add(tool)

    def set_tool_enabled(self, tool: MCPToolCache, enabled: bool) -> None:
        tool.enabled = 1 if enabled else 0

    def set_last_connected(self, server: MCPServer, timestamp: str) -> None:
        server.last_connected_at = timestamp
