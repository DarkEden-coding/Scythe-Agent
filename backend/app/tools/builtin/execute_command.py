from __future__ import annotations

import asyncio
from pathlib import Path

from app.tools.contracts import ToolResult
from app.tools.path_utils import resolve_path

_BLOCKED_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "> /dev/sd",
    "chmod -R 777 /",
    "shutdown",
    "reboot",
    "halt",
    "init 0",
    "init 6",
]

_MAX_OUTPUT_BYTES = 100 * 1024  # 100KB


class ExecuteCommandTool:
    name = "execute_command"
    description = (
        "Execute a local command. cwd must be an absolute path when provided (e.g. /path/to/project)."
    )
    input_schema = {
        "type": "object",
        "required": ["command"],
        "properties": {
            "command": {"type": "string"},
            "cwd": {"type": "string"},
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "default": 30,
            },
        },
    }

    async def run(
        self,
        payload: dict,
        *,
        project_root: str | None = None,
        chat_id: str | None = None,
        chat_repo=None,
    ) -> ToolResult:
        command = str(payload.get("command", "")).strip()
        cwd_raw = payload.get("cwd") or None
        timeout = min(int(payload.get("timeout", 30)), 120)
        if not command:
            return ToolResult(output="Missing command", file_edits=[], ok=False)

        cwd = None
        if cwd_raw:
            try:
                cwd = str(resolve_path(cwd_raw.strip(), project_root=project_root))
            except ValueError as exc:
                return ToolResult(output=str(exc), file_edits=[], ok=False)
        elif project_root:
            cwd = str(Path(project_root).resolve())

        # Check blocklist
        cmd_lower = command.lower()
        for pattern in _BLOCKED_PATTERNS:
            if pattern in cmd_lower:
                return ToolResult(
                    output=f"Blocked: command matches restricted pattern '{pattern}'",
                    file_edits=[],
                    ok=False,
                )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return ToolResult(
                output=f"Command timed out after {timeout}s",
                file_edits=[],
                ok=False,
            )
        except Exception as exc:
            return ToolResult(output=f"Command failed: {exc}", file_edits=[], ok=False)

        out = (
            (stdout or b"")[:_MAX_OUTPUT_BYTES]
            .decode("utf-8", errors="replace")
            .strip()
        )
        err = (
            (stderr or b"")[:_MAX_OUTPUT_BYTES]
            .decode("utf-8", errors="replace")
            .strip()
        )
        payload_out = out if out else ""
        if err:
            payload_out = f"{payload_out}\n{err}".strip()
        return ToolResult(output=payload_out, file_edits=[])
