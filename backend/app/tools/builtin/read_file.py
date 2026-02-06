from __future__ import annotations

from pathlib import Path

from app.tools.contracts import ToolResult


class ReadFileTool:
    name = "read_file"
    description = "Read a file from workspace."
    input_schema = {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}}

    async def run(self, payload: dict) -> ToolResult:
        path = Path(payload.get("path", ""))
        if not path.exists() or not path.is_file():
            return ToolResult(output=f"File not found: {path}", file_edits=[])
        return ToolResult(output=path.read_text(encoding="utf-8"), file_edits=[])

