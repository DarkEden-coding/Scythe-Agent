from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.mcp_server import MCPServer
from app.db.models.mcp_tool_cache import MCPToolCache


class MCPRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_enabled_servers(self) -> list[MCPServer]:
        stmt = (
            select(MCPServer)
            .where(MCPServer.enabled == 1)
            .order_by(MCPServer.name.asc(), MCPServer.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_server(self, server_id: str) -> MCPServer | None:
        return self.db.get(MCPServer, server_id)

    def list_cached_tools(self) -> list[MCPToolCache]:
        stmt = select(MCPToolCache).order_by(MCPToolCache.tool_name.asc(), MCPToolCache.id.asc())
        return list(self.db.scalars(stmt).all())

    def list_cached_tools_for_server(self, server_id: str) -> list[MCPToolCache]:
        stmt = (
            select(MCPToolCache)
            .where(MCPToolCache.server_id == server_id)
            .order_by(MCPToolCache.tool_name.asc(), MCPToolCache.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def replace_server_tools(self, *, server_id: str, tools: list[MCPToolCache]) -> None:
        self.db.execute(delete(MCPToolCache).where(MCPToolCache.server_id == server_id))
        for tool in tools:
            self.db.add(tool)

    def set_last_connected(self, server: MCPServer, timestamp: str) -> None:
        server.last_connected_at = timestamp

    def commit(self) -> None:
        self.db.commit()
