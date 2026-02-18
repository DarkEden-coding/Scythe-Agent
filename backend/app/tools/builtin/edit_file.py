from __future__ import annotations

import difflib
from pathlib import Path

from app.tools.contracts import ToolFileEdit, ToolResult
from app.tools.path_utils import resolve_path


class EditFileTool:
    name = "edit_file"
    description = "Write content to a file. path must be an absolute path (e.g. /path/to/project/src/main.py)."
    input_schema = {
        "type": "object",
        "required": ["path", "content"],
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
    }

    async def run(
        self, payload: dict, *, project_root: str | None = None
    ) -> ToolResult:
        try:
            target = resolve_path(payload.get("path", ""), project_root=project_root)
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
            diff_lines = list(
                difflib.unified_diff(
                    previous.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile="before",
                    tofile="after",
                    n=3,
                )
            )
            diff = "".join(diff_lines[:100])

        file_edit = ToolFileEdit(file_path=str(target), action=action, diff=diff, original_content=previous)
        return ToolResult(output=f"{action} {target}", file_edits=[file_edit])
