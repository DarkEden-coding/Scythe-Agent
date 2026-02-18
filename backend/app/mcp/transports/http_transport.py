"""MCP HTTP transport: POST JSON-RPC to a URL, receive JSON response."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class HttpTransport:
    """Connects to an MCP server via HTTP POST (JSON-RPC request/response)."""

    def __init__(self, config: dict[str, Any]) -> None:
        url = config.get("url") or ""
        self._url = url.rstrip("/")
        headers = config.get("headers")
        self._headers = dict(headers) if isinstance(headers, dict) else {}
        self._request_id = 0
        self._init_done = False

    async def connect(self) -> None:
        """Complete MCP initialize handshake."""
        if self._init_done:
            return
        init_result = await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "scythe-agent", "version": "0.1.0"},
            },
        )
        if not init_result:
            raise RuntimeError("Initialize failed: no response")
        await self._send_notification("notifications/initialized")
        self._init_done = True

    async def request(self, method: str, params: dict | None = None) -> dict:
        """Send JSON-RPC request and return the result payload."""
        if not self._init_done:
            await self.connect()
        result = await self._send_request(method, params or {})
        if result is None:
            return {}
        return result if isinstance(result, dict) else {}

    async def close(self) -> None:
        """No-op for HTTP (stateless)."""
        self._init_done = False

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _send_notification(self, method: str) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        await self._post(msg)

    async def _send_request(self, method: str, params: dict) -> dict | None:
        req_id = self._next_id()
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        resp = await self._post(msg)
        if resp is None:
            return None
        if "error" in resp:
            err = resp["error"]
            raise RuntimeError(err.get("message", str(err)))
        return resp.get("result")

    async def _post(self, payload: dict) -> dict | None:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self._headers,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self._url, json=payload, headers=headers)
                response.raise_for_status()
                body = response.text or ""
                if not body.strip():
                    logger.warning("MCP HTTP empty response: url=%s status=%s", self._url, response.status_code)
                    raise RuntimeError(
                        f"Empty response from {self._url} (status {response.status_code})"
                    )
                try:
                    return json.loads(body)
                except json.JSONDecodeError as e:
                    if body.strip().startswith("data:"):
                        raw = body.strip()[5:].split("\n")[0].strip()
                        if raw:
                            try:
                                return json.loads(raw)
                            except json.JSONDecodeError:
                                pass
                    preview = body[:500].replace("\n", " ")
                    if len(body) > 500:
                        preview += "..."
                    logger.warning(
                        "MCP HTTP invalid JSON: url=%s status=%s body_len=%d preview=%s",
                        self._url, response.status_code, len(body), preview[:100],
                    )
                    raise RuntimeError(
                        f"Invalid JSON from server (status {response.status_code}). "
                        f"Body: {preview}"
                    ) from e
        except httpx.HTTPStatusError as e:
            body = (e.response.text or "")[:300]
            raise RuntimeError(
                f"HTTP {e.response.status_code} from {self._url}: {body}"
            ) from e
