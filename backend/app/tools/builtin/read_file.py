from __future__ import annotations

from pathlib import Path

from app.tools.contracts import ToolResult

_BLOCKED_PREFIXES = ["/etc", "/var", "/usr", "/bin", "/sbin", "/boot", "/proc", "/sys", "/dev"]


def _validate_path(path_str: str) -> Path:
    resolved = Path(path_str).resolve()
    for prefix in _BLOCKED_PREFIXES:
        if str(resolved).startswith(prefix):
            raise ValueError(f"Access denied: {path_str} is in a restricted directory")
    return resolved


class ReadFileTool:
    name = "read_file"
    description = "Read a file from workspace."
    input_schema = {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}}

    async def run(self, payload: dict) -> ToolResult:
        try:
            path = _validate_path(payload.get("path", ""))
        except ValueError as exc:
            return ToolResult(output=str(exc), file_edits=[])
        if not path.exists() or not path.is_file():
            return ToolResult(output=f"File not found: {path}", file_edits=[])
        return ToolResult(output=path.read_text(encoding="utf-8"), file_edits=[])
