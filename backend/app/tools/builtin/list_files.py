from __future__ import annotations

from pathlib import Path

from app.tools.contracts import ToolResult

_BLOCKED_PREFIXES = ["/etc", "/var", "/usr", "/bin", "/sbin", "/boot", "/proc", "/sys", "/dev"]
_MAX_ENTRIES = 1000


def _validate_path(path_str: str) -> Path:
    resolved = Path(path_str).resolve()
    for prefix in _BLOCKED_PREFIXES:
        if str(resolved).startswith(prefix):
            raise ValueError(f"Access denied: {path_str} is in a restricted directory")
    return resolved


class ListFilesTool:
    name = "list_files"
    description = "List files in a directory."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "recursive": {"type": "boolean"},
        },
    }

    async def run(self, payload: dict) -> ToolResult:
        try:
            base = _validate_path(payload.get("path", "."))
        except ValueError as exc:
            return ToolResult(output=str(exc), file_edits=[])
        if not base.exists() or not base.is_dir():
            return ToolResult(output=f"Directory not found: {base}", file_edits=[])
        iterator = base.rglob("*") if bool(payload.get("recursive", False)) else base.iterdir()
        items = []
        for p in iterator:
            items.append(str(p))
            if len(items) >= _MAX_ENTRIES:
                items.append(f"... truncated at {_MAX_ENTRIES} entries")
                break
        items.sort()
        return ToolResult(output="\n".join(items), file_edits=[])
