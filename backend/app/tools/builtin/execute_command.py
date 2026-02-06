from __future__ import annotations

import subprocess

from app.tools.contracts import ToolResult


class ExecuteCommandTool:
    name = "execute_command"
    description = "Execute a local command with basic safeguards."
    input_schema = {
        "type": "object",
        "required": ["command"],
        "properties": {
            "command": {"type": "string"},
            "cwd": {"type": "string"},
        },
    }

    async def run(self, payload: dict) -> ToolResult:
        command = str(payload.get("command", "")).strip()
        cwd = payload.get("cwd")
        if not command:
            return ToolResult(output="Missing command", file_edits=[])
        completed = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        out = completed.stdout.strip()
        err = completed.stderr.strip()
        payload_out = out if out else ""
        if err:
            payload_out = f"{payload_out}\n{err}".strip()
        return ToolResult(output=payload_out, file_edits=[])

