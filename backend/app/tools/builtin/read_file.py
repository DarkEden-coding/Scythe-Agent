from __future__ import annotations

from app.tools.contracts import ToolResult
from app.tools.path_utils import resolve_path
from app.utils.file_structure import get_file_structure


class ReadFileTool:
    name = "read_file"
    description = (
        "Read a file from the project. path must be an absolute path. "
        "Without start/end: returns file structure (declarations with line ranges). "
        "With start and end (1-based): returns that line span. Use structure first, then read specific spans."
    )
    input_schema = {
        "type": "object",
        "required": ["path"],
        "properties": {
            "path": {"type": "string"},
            "start": {"type": "integer", "description": "Start line (1-based). Omit with end to get structure."},
            "end": {"type": "integer", "description": "End line (1-based). Omit with start to get structure."},
        },
    }

    async def run(
        self, payload: dict, *, project_root: str | None = None
    ) -> ToolResult:
        try:
            path = resolve_path(payload.get("path", ""), project_root=project_root)
        except ValueError as exc:
            return ToolResult(output=str(exc), file_edits=[], ok=False)
        if not path.exists() or not path.is_file():
            return ToolResult(output=f"File not found: {path}", file_edits=[], ok=False)

        start_val = payload.get("start")
        end_val = payload.get("end")
        has_span = start_val is not None and end_val is not None

        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()

        if has_span and start_val is not None and end_val is not None:
            try:
                start_idx = int(start_val)
                end_idx = int(end_val)
            except (TypeError, ValueError):
                return ToolResult(
                    output="start and end must be integers (1-based line numbers).",
                    file_edits=[],
                    ok=False,
                )
            if start_idx < 1 or end_idx < 1:
                return ToolResult(
                    output="start and end must be >= 1 (1-based line numbers).",
                    file_edits=[],
                    ok=False,
                )
            start_idx = min(start_idx, len(lines))
            end_idx = min(end_idx, len(lines))
            if start_idx > end_idx:
                start_idx, end_idx = end_idx, start_idx
            span_lines = lines[start_idx - 1 : end_idx]
            return ToolResult(
                output="\n".join(span_lines),
                file_edits=[],
            )

        return ToolResult(
            output=get_file_structure(content, str(path)),
            file_edits=[],
        )
