"""Read file tool — project files, tool outputs, targeted spans."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.types import ToolExecutionResult
from app.tools.path_utils import resolve_path
from app.utils.file_structure import get_file_structure

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})
EXT_TO_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


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


async def _handler(payload: dict, context: ToolExecutionContext) -> ToolExecutionResult:
    try:
        path = resolve_path(
            payload.get("path", ""),
            project_root=context.project_root,
            allow_external=True,
        )
    except ValueError as exc:
        return ToolExecutionResult(output=str(exc), file_edits=[], ok=False)
    if not path.exists() or not path.is_file():
        return ToolExecutionResult(output=f"File not found: {path}", file_edits=[], ok=False)

    if path.suffix.lower() in IMAGE_EXTENSIONS:
        if context.model_has_vision:
            def _read_image_base64(p: Path) -> str:
                data = p.read_bytes()
                b64 = base64.b64encode(data).decode("ascii")
                mime = EXT_TO_MIME.get(p.suffix.lower(), "image/png")
                return f"data:{mime};base64,{b64}"
            data_url = await asyncio.to_thread(_read_image_base64, path)
            return ToolExecutionResult(
                output=f"Image: {path}\n\n{data_url}",
                file_edits=[],
            )
        return ToolExecutionResult(
            output=(
                f"Image file at {path} "
                "(model does not support vision; cannot analyze image content)."
            ),
            file_edits=[],
        )

    is_mention_ref = bool(payload.get("__mention_reference__"))
    start_val = payload.get("start")
    end_val = payload.get("end")
    has_span = start_val is not None and end_val is not None

    if is_mention_ref and not has_span:
        lines = path.read_text(encoding="utf-8").splitlines()
        total = len(lines)
        if total > 0:
            output = await asyncio.to_thread(_read_span_streaming, path, 1, total)
            return ToolExecutionResult(output=output, file_edits=[])

    if has_span and start_val is not None and end_val is not None:
        try:
            start_idx = int(start_val)
            end_idx = int(end_val)
        except (TypeError, ValueError):
            return ToolExecutionResult(
                output="start and end must be integers (1-based line numbers).",
                file_edits=[],
                ok=False,
            )
        if start_idx < 1 or end_idx < 1:
            return ToolExecutionResult(
                output="start and end must be >= 1 (1-based line numbers).",
                file_edits=[],
                ok=False,
            )
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx
        output = await asyncio.to_thread(_read_span_streaming, path, start_idx, end_idx)
        return ToolExecutionResult(output=output, file_edits=[])

    output = await asyncio.to_thread(_read_structure, path)
    return ToolExecutionResult(output=output, file_edits=[])


TOOL_PLUGIN = ToolPlugin(
    name="read_file",
    description=(
        "Read a file or image. path must be absolute. Can read project files, tool output files "
        "(spilled outputs under tool_outputs/), and other external paths (those require approval). "
        "Supports text files (.py, .ts, .js, etc.) and images (.png, .jpg, .gif, .webp)—images are returned "
        "as base64 when the model supports vision. "
        "Without start/end: returns file structure (declarations with line ranges) and total line count; use that to decide which spans to read. "
        "With start and end (1-based): returns that line span. "
        "For files without structure support (unknown extensions), use start/end to read sections. Always prefer targeted spans over reading entire large files."
    ),
    input_schema={
        "type": "object",
        "required": ["path"],
        "properties": {
            "path": {"type": "string"},
            "start": {"type": "integer", "description": "Start line (1-based). Omit with end to get structure."},
            "end": {"type": "integer", "description": "End line (1-based). Omit with start to get structure."},
        },
    },
    approval_policy="rules",
    handler=_handler,
)
