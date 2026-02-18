from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.orm import Session

from app.db.models.mcp_tool_cache import MCPToolCache

MCP_TOOL_CACHE_TTL_SECONDS = 300
from app.db.repositories.mcp_repo import MCPRepository
from app.mcp.protocol_models import (
    MCPToolCallResult,
    MCPToolDescriptor,
    parse_tool_call_result,
    parse_tools_list_response,
)
# Production has no built-in transports; tests register mock factories via register_transport_factory
_transport_factory_registry: dict[str, type] = {}


class _Transport(Protocol):
    async def connect(self) -> None: ...

    async def request(self, method: str, params: dict | None = None) -> dict: ...

    async def close(self) -> None: ...


class MCPClientManager:
    def __init__(self):
        self._transports: dict[str, _Transport] = {}
        self._server_configs: dict[str, tuple[str, dict]] = {}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _build_transport(self, *, transport_name: str, config: dict) -> _Transport:
        key = transport_name.lower().strip()
        factory = _transport_factory_registry.get(key)
        if factory is not None:
            return factory(config)
        raise NotImplementedError(f"No transport factory registered for: {transport_name}")

    @staticmethod
    def register_transport_factory(name: str, factory: type) -> None:
        """Register a transport factory for tests. name is e.g. 'stdio', 'sse', 'http'."""
        _transport_factory_registry[name.lower().strip()] = factory

    def _server_cache_is_fresh(self, repo: MCPRepository, server_id: str) -> bool:
        """Return True if server has cached tools within TTL."""
        cached = repo.list_cached_tools_for_server(server_id)
        if not cached:
            return False
        try:
            newest = max(c.discovered_at for c in cached)
            discovered = datetime.fromisoformat(newest.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - discovered).total_seconds() < MCP_TOOL_CACHE_TTL_SECONDS
        except (ValueError, TypeError):
            return False

    async def discover_and_cache_tools(
        self, db: Session, *, force_refresh: bool = False
    ) -> tuple[list[MCPToolDescriptor], list[str]]:
        repo = MCPRepository(db)
        discovered: list[MCPToolDescriptor] = []
        errors: list[str] = []
        servers = repo.list_enabled_servers()
        for server in servers:
            try:
                config = json.loads(server.config_json)
                if not isinstance(config, dict):
                    config = {}
            except json.JSONDecodeError:
                config = {}
            self._server_configs[server.id] = (server.transport, config)

            if not force_refresh and self._server_cache_is_fresh(repo, server.id):
                for cached in repo.list_cached_tools_for_server(server.id):
                    schema = {}
                    try:
                        schema_value = json.loads(cached.schema_json)
                        if isinstance(schema_value, dict):
                            schema = schema_value
                    except json.JSONDecodeError:
                        pass
                    discovered.append(
                        MCPToolDescriptor(
                            server_id=server.id,
                            name=cached.tool_name,
                            description=cached.description,
                            input_schema=schema,
                        )
                    )
                continue

            try:
                transport = self._build_transport(transport_name=server.transport, config=config)
                await transport.connect()
                self._transports[server.id] = transport
                raw = await transport.request("tools/list", {})
                tools = parse_tools_list_response(raw, server_id=server.id)
                cache_rows = [
                    MCPToolCache(
                        id=f"mcpt-{server.id}-{tool.name}",
                        server_id=server.id,
                        tool_name=tool.name,
                        schema_json=json.dumps(tool.input_schema, sort_keys=True),
                        description=tool.description,
                        discovered_at=self._now(),
                    )
                    for tool in tools
                ]
                repo.replace_server_tools(server_id=server.id, tools=cache_rows)
                repo.set_last_connected(server, self._now())
                discovered.extend(tools)
            except Exception as exc:
                errors.append(f"{server.id}: {exc}")
                for cached in repo.list_cached_tools_for_server(server.id):
                    schema = {}
                    try:
                        schema_value = json.loads(cached.schema_json)
                        if isinstance(schema_value, dict):
                            schema = schema_value
                    except json.JSONDecodeError:
                        schema = {}
                    discovered.append(
                        MCPToolDescriptor(
                            server_id=server.id,
                            name=cached.tool_name,
                            description=cached.description,
                            input_schema=schema,
                        )
                    )
            finally:
                repo.commit()
        return discovered, errors

    async def call_tool(self, server_id: str, tool_name: str, payload: dict) -> MCPToolCallResult:
        transport = self._transports.get(server_id)
        if transport is None:
            server_config = self._server_configs.get(server_id)
            if server_config is None:
                raise ValueError(f"MCP server not available: {server_id}")
            transport_name, config = server_config
            transport = self._build_transport(transport_name=transport_name, config=config)
            await transport.connect()
            self._transports[server_id] = transport
        raw = await transport.request("tools/call", {"name": tool_name, "arguments": payload})
        return parse_tool_call_result(raw)


_manager: MCPClientManager | None = None


def get_mcp_client_manager() -> MCPClientManager:
    global _manager
    if _manager is None:
        _manager = MCPClientManager()
    return _manager


def reset_mcp_client_manager() -> None:
    global _manager
    _manager = None
