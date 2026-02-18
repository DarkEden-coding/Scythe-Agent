from __future__ import annotations

from pathlib import Path

from app.tools.contracts import ToolResult
from app.tools.path_utils import resolve_path

_MAX_ENTRIES = 1000


class ListFilesTool:
    name = "list_files"
    description = "List files in a directory. path must be an absolute path (e.g. /path/to/project). Omit to list project root."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "recursive": {"type": "boolean"},
        },
    }

    async def run(
        self, payload: dict, *, project_root: str | None = None
    ) -> ToolResult:
        path_raw = payload.get("path") or ""
        if not path_raw or path_raw.strip() == ".":
            if not project_root:
                return ToolResult(
                    output="path is required when no project is selected; use an absolute path.",
                    file_edits=[],
                )
            path_raw = str(Path(project_root).resolve())
        try:
            base = resolve_path(path_raw.strip(), project_root=project_root)
        except ValueError as exc:
            return ToolResult(output=str(exc), file_edits=[])
        if not base.exists() or not base.is_dir():
            return ToolResult(output=f"Directory not found: {base}", file_edits=[])
        iterator = (
            base.rglob("*") if bool(payload.get("recursive", False)) else base.iterdir()
        )
        items = []
        for p in iterator:
            items.append(str(p))
            if len(items) >= _MAX_ENTRIES:
                items.append(f"... truncated at {_MAX_ENTRIES} entries")
                break
        items.sort()
        return ToolResult(output="\n".join(items), file_edits=[])
