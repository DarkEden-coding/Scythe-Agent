from __future__ import annotations

import difflib
from pathlib import Path

from app.tools.contracts import ToolFileEdit, ToolResult

_BLOCKED_PREFIXES = ["/etc", "/var", "/usr", "/bin", "/sbin", "/boot", "/proc", "/sys", "/dev"]


def _validate_path(path_str: str) -> Path:
    resolved = Path(path_str).resolve()
    for prefix in _BLOCKED_PREFIXES:
        if str(resolved).startswith(prefix):
            raise ValueError(f"Access denied: {path_str} is in a restricted directory")
    return resolved


class EditFileTool:
    name = "edit_file"
    description = "Write content to a file."
    input_schema = {
        "type": "object",
        "required": ["path", "content"],
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
    }

    async def run(self, payload: dict) -> ToolResult:
        try:
            target = _validate_path(payload.get("path", ""))
        except ValueError as exc:
            return ToolResult(output=str(exc), file_edits=[])

        content = str(payload.get("content", ""))
        action = "created"
        previous = None
        if target.exists():
            previous = target.read_text(encoding="utf-8")
            if previous == content:
                return ToolResult(output=f"unchanged {target}", file_edits=[])
            action = "modified"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        diff = None
        if previous is not None:
            diff_lines = list(difflib.unified_diff(
                previous.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile="before",
                tofile="after",
                n=3,
            ))
            diff = "".join(diff_lines[:100])

        file_edit = ToolFileEdit(file_path=str(target), action=action, diff=diff)
        return ToolResult(output=f"{action} {target}", file_edits=[file_edit])
