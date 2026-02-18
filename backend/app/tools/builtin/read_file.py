from __future__ import annotations

from app.tools.contracts import ToolResult
from app.tools.path_utils import resolve_path


class ReadFileTool:
    name = "read_file"
    description = (
        "Read a file from the project. path must be an absolute path (e.g. /path/to/project/src/main.py)."
    )
    input_schema = {
        "type": "object",
        "required": ["path"],
        "properties": {"path": {"type": "string"}},
    }

    async def run(
        self, payload: dict, *, project_root: str | None = None
    ) -> ToolResult:
        try:
            path = resolve_path(payload.get("path", ""), project_root=project_root)
        except ValueError as exc:
            return ToolResult(output=str(exc), file_edits=[])
        if not path.exists() or not path.is_file():
            return ToolResult(output=f"File not found: {path}", file_edits=[])
        return ToolResult(output=path.read_text(encoding="utf-8"), file_edits=[])
