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
        await self._post(msg, allow_empty_response=True)

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

    async def _post(self, payload: dict, *, allow_empty_response: bool = False) -> dict | None:
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
                    if allow_empty_response:
                        return None
                    logger.warning("MCP HTTP empty response: url=%s status=%s", self._url, response.status_code)
                    raise RuntimeError(
                        f"Empty response from {self._url} (status {response.status_code})"
                    )
                try:
                    return json.loads(body)
                except json.JSONDecodeError as e:
                    sse_payload = self._extract_json_from_sse(body)
                    if sse_payload is not None:
                        return sse_payload
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

    @staticmethod
    def _extract_json_from_sse(body: str) -> dict | None:
        # Support SSE-framed MCP responses such as:
        # event: message
        # data: {"jsonrpc":"2.0", ...}
        normalized = body.replace("\r\n", "\n").replace("\r", "\n")
        blocks = normalized.split("\n\n")
        for block in blocks:
            if not block.strip():
                continue
            data_lines: list[str] = []
            for line in block.split("\n"):
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
            if not data_lines:
                continue
            payload = "\n".join(data_lines).strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None
