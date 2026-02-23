"""MCP stdio transport: spawn subprocess and communicate via JSON-RPC over stdin/stdout."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any


class StdioTransport:
    """Connects to an MCP server via subprocess stdio using JSON-RPC 2.0."""

    def __init__(self, config: dict[str, Any]) -> None:
        command = config.get("command") or "npx"
        args_in = config.get("args")
        args = [str(a) for a in args_in] if isinstance(args_in, list) else []
        self._argv: list[str] = [command, *args]
        env_in = config.get("env")
        if isinstance(env_in, dict):
            self._env = dict(os.environ)
            for k, v in env_in.items():
                if k and v is not None:
                    self._env[str(k)] = str(v)
        else:
            self._env = None
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._init_done = False

    async def connect(self) -> None:
        """Spawn subprocess and complete MCP initialize handshake."""
        if self._process is not None and self._process.returncode is None:
            return
        kwargs: dict[str, Any] = {
            "stdin": asyncio.subprocess.PIPE,
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }
        if self._env is not None:
            kwargs["env"] = self._env
        self._process = await asyncio.create_subprocess_exec(
            *self._argv,
            **kwargs,
        )
        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("Subprocess stdin/stdout not available")
        try:
            init_result = await self._send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "scythe-agent", "version": "0.1.0"},
                },
            )
            if init_result is None:
                raise RuntimeError("Initialize failed: no response")
            await self._send_notification("notifications/initialized")
            self._init_done = True
        except Exception:
            await self.close()
            raise

    async def request(self, method: str, params: dict | None = None) -> dict:
        """Send JSON-RPC request and return the result payload."""
        if not self._init_done:
            await self.connect()
        result = await self._send_request(method, params or {})
        if result is None:
            return {}
        return result if isinstance(result, dict) else {}

    async def close(self) -> None:
        """Terminate the subprocess."""
        if self._process is None:
            return
        try:
            self._process.terminate()
            await asyncio.wait_for(self._process.wait(), timeout=2.0)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                self._process.kill()
            except ProcessLookupError:
                pass
        finally:
            self._process = None
            self._init_done = False

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _send_notification(self, method: str) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        line = json.dumps(msg) + "\n"
        if self._process and self._process.stdin:
            self._process.stdin.write(line.encode())
            await self._process.stdin.drain()

    async def _send_request(self, method: str, params: dict) -> dict | None:
        req_id = self._next_id()
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        line = json.dumps(msg) + "\n"
        if not self._process or not self._process.stdin or not self._process.stdout:
            return None
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()
        while True:
            out_line = await self._process.stdout.readline()
            if not out_line:
                return None
            try:
                resp = json.loads(out_line.decode().strip())
            except json.JSONDecodeError:
                continue
            if resp.get("id") == req_id:
                if "error" in resp:
                    err = resp["error"]
                    raise RuntimeError(err.get("message", str(err)))
                return resp.get("result")
            if "method" in resp and resp.get("method") == "notifications/cancelled":
                continue
        return None
