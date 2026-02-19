from __future__ import annotations

import asyncio
from pathlib import Path

from app.tools.contracts import ToolResult
from app.tools.path_utils import resolve_path
from app.utils.file_structure import get_file_structure


def _read_span_streaming(path: Path, start_idx: int, end_idx: int) -> str:
    """Stream lines and collect only the requested span; stop after end_idx to save I/O."""
    span_lines: list[str] = []
    total = 0
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            line_num = i + 1
            total = line_num
            if line_num > end_idx:
                break
            if line_num >= start_idx:
                span_lines.append(line.rstrip("\n"))
    total_str = f"lines {start_idx}-{end_idx}" if total > end_idx else f"{total} lines"
    return f"File: {path} ({total_str})\n\n" + "\n".join(span_lines)


def _read_structure(path: Path) -> str:
    """Read file and return structure; runs in thread."""
    content = path.read_text(encoding="utf-8")
    return get_file_structure(content, str(path))


class ReadFileTool:
    name = "read_file"
    description = (
        "Read a file. path must be absolute. Can read project files, tool output files "
        "(spilled outputs under tool_outputs/), and other external paths (those require approval). "
        "Without start/end: returns file structure (declarations with line ranges) and total line count; use that to decide which spans to read. "
        "With start and end (1-based): returns that line span. "
        "For files without structure support (unknown extensions), use start/end to read sections. Always prefer targeted spans over reading entire large files."
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
            path = resolve_path(
                payload.get("path", ""),
                project_root=project_root,
                allow_external=True,
            )
        except ValueError as exc:
            return ToolResult(output=str(exc), file_edits=[], ok=False)
        if not path.exists() or not path.is_file():
            return ToolResult(output=f"File not found: {path}", file_edits=[], ok=False)

        start_val = payload.get("start")
        end_val = payload.get("end")
        has_span = start_val is not None and end_val is not None

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
            if start_idx > end_idx:
                start_idx, end_idx = end_idx, start_idx
            output = await asyncio.to_thread(_read_span_streaming, path, start_idx, end_idx)
            return ToolResult(output=output, file_edits=[])

        output = await asyncio.to_thread(_read_structure, path)
        return ToolResult(output=output, file_edits=[])
