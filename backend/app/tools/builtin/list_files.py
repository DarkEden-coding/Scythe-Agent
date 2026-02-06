from __future__ import annotations

from pathlib import Path

from app.tools.contracts import ToolResult


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
        base = Path(payload.get("path", "."))
        recursive = bool(payload.get("recursive", False))
        if not base.exists() or not base.is_dir():
            return ToolResult(output=f"Directory not found: {base}", file_edits=[])
        iterator = base.rglob("*") if recursive else base.iterdir()
        items = [str(p) for p in iterator]
        items.sort()
        return ToolResult(output="\n".join(items), file_edits=[])

