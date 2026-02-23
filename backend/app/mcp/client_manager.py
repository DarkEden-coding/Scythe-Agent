from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.container import get_container
from app.db.models.mcp_tool_cache import MCPToolCache
from app.db.repositories.mcp_repo import MCPRepository
from app.mcp.protocol_models import (
    MCPToolCallResult,
    MCPToolDescriptor,
    parse_tool_call_result,
    parse_tools_list_response,
)

logger = logging.getLogger(__name__)
MCP_SERVER_STARTUP_TIMEOUT_SECONDS = 10
MCP_TOOL_CACHE_TTL_SECONDS = 300
# Transports are registered at import time (stdio, http); tests can override via register_transport_factory
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
        if key == "streamable-http":
            key = "http"
        factory = _transport_factory_registry.get(key)
        if factory is not None:
            return factory(config)
        raise NotImplementedError(f"No transport factory registered for: {transport_name}")

    @staticmethod
    def register_transport_factory(name: str, factory: type) -> None:
        """Register a transport factory. name is e.g. 'stdio', 'http'."""
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
                for cached in repo.list_cached_tools_for_server(
                    server.id, enabled_only=True
                ):
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
                await asyncio.wait_for(
                    transport.connect(), timeout=MCP_SERVER_STARTUP_TIMEOUT_SECONDS
                )
                self._transports[server.id] = transport
                raw = await transport.request("tools/list", {})
                tools = parse_tools_list_response(raw, server_id=server.id)
                existing = {t.tool_name: t for t in repo.list_cached_tools_for_server(server.id)}
                cache_rows = []
                for tool in tools:
                    prev = existing.get(tool.name)
                    enabled = prev.enabled if prev else 1
                    cache_rows.append(
                        MCPToolCache(
                            id=f"mcpt-{server.id}-{tool.name}",
                            server_id=server.id,
                            tool_name=tool.name,
                            schema_json=json.dumps(tool.input_schema, sort_keys=True),
                            description=tool.description,
                            discovered_at=self._now(),
                            enabled=enabled,
                        )
                    )
                repo.replace_server_tools(server_id=server.id, tools=cache_rows)
                repo.set_last_connected(server, self._now())
                for i, tool in enumerate(tools):
                    if cache_rows[i].enabled:
                        discovered.append(tool)
            except Exception as exc:
                base = str(exc)
                if "Expecting value" in base or (type(exc).__name__ == "JSONDecodeError"):
                    base = f"Server returned invalid/empty response. Original: {base}"
                msg = f"{server.id}: {base}"
                errors.append(msg)
                logger.warning("MCP discovery failed for server %s: %s", server.id, exc)
                for cached in repo.list_cached_tools_for_server(
                    server.id, enabled_only=True
                ):
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
            await asyncio.wait_for(
                transport.connect(), timeout=MCP_SERVER_STARTUP_TIMEOUT_SECONDS
            )
            self._transports[server_id] = transport
        raw = await transport.request("tools/call", {"name": tool_name, "arguments": payload})
        return parse_tool_call_result(raw)

def get_mcp_client_manager() -> MCPClientManager:
    container = get_container()
    if container is None:
        raise RuntimeError("AppContainer is not initialized")
    return container.mcp_client_manager


def reset_mcp_client_manager() -> None:
    container = get_container()
    if container is None:
        return
    container.mcp_client_manager = MCPClientManager()
