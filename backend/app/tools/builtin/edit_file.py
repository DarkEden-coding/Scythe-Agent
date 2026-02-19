"""Search-and-replace file edit tool with exact and fuzzy matching."""

from __future__ import annotations

import asyncio
import difflib
import re
from pathlib import Path

from app.tools.contracts import ToolFileEdit, ToolResult
from app.tools.path_utils import resolve_path

_PADDING_LINES = 5


def _fuzzy_pattern(search: str) -> re.Pattern[str]:
    """Build regex that treats any whitespace (tabs, spaces) interchangeably."""
    parts = [p for p in re.split(r"\s+", search) if p]
    if not parts:
        return re.compile(re.escape(search))
    pattern = r"\s+".join(re.escape(p) for p in parts)
    return re.compile(pattern)


def _extract_context(content: str, start_char: int, end_char: int) -> str:
    """Extract edit region plus PADDING_LINES on both sides."""
    lines = content.splitlines(keepends=True)
    if not lines:
        return ""

    pos = 0
    line_indices: list[tuple[int, int, int]] = []  # (line_idx, start, end)
    for i, line in enumerate(lines):
        line_start = pos
        line_end = pos + len(line)
        line_indices.append((i, line_start, line_end))
        pos = line_end

    start_line_idx = 0
    end_line_idx = len(line_indices) - 1
    for i, (_, line_start, line_end) in enumerate(line_indices):
        if start_char < line_end:
            start_line_idx = i
            break
    for i in range(len(line_indices) - 1, -1, -1):
        _, line_start, line_end = line_indices[i]
        if end_char > line_start:
            end_line_idx = i
            break

    from_idx = max(0, start_line_idx - _PADDING_LINES)
    to_idx = min(len(lines), end_line_idx + 1 + _PADDING_LINES)
    return "".join(lines[from_idx:to_idx]).rstrip()


def _apply_replace(
    content: str, search: str, replace: str, *, fuzzy: bool
) -> tuple[str, int, int] | None:
    """
    Perform search-and-replace. Returns (new_content, start, end) or None if not found.
    start/end are char offsets of the replaced region in the new content.
    """
    if fuzzy:
        pattern = _fuzzy_pattern(search)
        match = pattern.search(content)
        if match is None:
            return None
        start, end = match.span()
        new_content = content[:start] + replace + content[end:]
        # Replaced region in new content: same start, different end
        new_end = start + len(replace)
        return (new_content, start, new_end)
    # Exact
    if search not in content:
        return None
    start = content.index(search)
    end = start + len(search)
    new_content = content[:start] + replace + content[end:]
    new_end = start + len(replace)
    return (new_content, start, new_end)


def _edit_file_sync(target: Path, search: str, replace: str) -> ToolResult:
    """Perform edit in sync context; runs in thread pool."""
    content = target.read_text(encoding="utf-8")
    used_fuzzy = False

    if not search:
        if content:
            return ToolResult(
                output="search must be non-empty",
                file_edits=[],
                ok=False,
            )
        result = (replace, 0, len(replace))
    else:
        result = _apply_replace(content, search, replace, fuzzy=False)
        if result is None:
            result = _apply_replace(content, search, replace, fuzzy=True)
            used_fuzzy = result is not None

    if result is None:
        return ToolResult(
            output="Search string not found (exact or fuzzy match).",
            file_edits=[],
            ok=False,
        )

    new_content, edit_start, edit_end = result
    if content == new_content:
        return ToolResult(output=f"unchanged {target}", file_edits=[])

    target.write_text(new_content, encoding="utf-8")

    diff_lines = list(
        difflib.unified_diff(
            content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile="before",
            tofile="after",
            n=3,
        )
    )
    diff = "".join(diff_lines[:100])
    file_edit = ToolFileEdit(
        file_path=str(target),
        action="modified",
        diff=diff,
        original_content=content,
    )

    output_parts = [f"modified {target}"]
    if used_fuzzy:
        output_parts.append(
            "Fuzzy search was used (whitespace/tab differences ignored)."
        )
        context = _extract_context(new_content, edit_start, edit_end)
        output_parts.append("\n--- edit result (±5 lines) ---")
        output_parts.append(context)
        output_parts.append("---")
    return ToolResult(output="\n".join(output_parts), file_edits=[file_edit])


class EditFileTool:
    name = "edit_file"
    description = (
        "Search-and-replace in a file. path must be absolute (e.g. /path/to/project/src/main.py). "
        "Tries exact match first; if not found, uses fuzzy match that ignores tab vs space differences. "
        "For empty files (e.g. after touch), use search=\"\" and replace=\"content\" to populate."
    )
    input_schema = {
        "type": "object",
        "required": ["path", "search", "replace"],
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "search": {
                "type": "string",
                "description": "Exact text to find and replace",
            },
            "replace": {
                "type": "string",
                "description": "Text to replace the match with",
            },
        },
    }

    async def run(
        self,
        payload: dict,
        *,
        project_root: str | None = None,
        chat_id: str | None = None,
        chat_repo=None,
    ) -> ToolResult:
        try:
            target = resolve_path(payload.get("path", ""), project_root=project_root)
        except ValueError as exc:
            return ToolResult(output=str(exc), file_edits=[], ok=False)

        search = str(payload.get("search", ""))
        replace = str(payload.get("replace", ""))

        if not target.exists():
            return ToolResult(output=f"File not found: {target}", file_edits=[], ok=False)

        return await asyncio.to_thread(_edit_file_sync, target, search, replace)
