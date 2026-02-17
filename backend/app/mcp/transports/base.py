"""MCP transport protocol for tool discovery and execution."""

from __future__ import annotations

from typing import Protocol


class MCPTransport(Protocol):
    """Protocol for MCP transport implementations."""

    async def connect(self) -> None: ...

    async def request(self, method: str, params: dict | None = None) -> dict: ...

    async def close(self) -> None: ...
