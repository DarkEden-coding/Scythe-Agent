from __future__ import annotations

import json
from typing import Any


class MCPHTTPTransport:
    """Minimal HTTP transport abstraction for local MVP tests."""

    def __init__(self, config: dict):
        self.config = config
        self._connected = False
        self._mock_responses: dict[str, dict[str, Any]] = {}

    async def connect(self) -> None:
        self._connected = True
        mock = self.config.get("mock_responses", {})
        if isinstance(mock, dict):
            self._mock_responses = {str(k): v for k, v in mock.items() if isinstance(v, dict)}

    async def request(self, method: str, params: dict | None = None) -> dict[str, Any]:
        if not self._connected:
            raise RuntimeError("MCP HTTP transport not connected")
        if method in self._mock_responses:
            return self._mock_responses[method]
        if method == "tools/list":
            tools = self.config.get("mock_tools", [])
            return {"tools": tools if isinstance(tools, list) else []}
        if method == "tools/call":
            payload = params or {}
            name = str(payload.get("name", ""))
            args = payload.get("arguments", {})
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"transport": "http", "tool": name, "args": args}, sort_keys=True),
                    }
                ]
            }
        raise RuntimeError(f"Unsupported MCP method for HTTP transport: {method}")

    async def close(self) -> None:
        self._connected = False

