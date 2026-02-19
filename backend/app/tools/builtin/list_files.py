from __future__ import annotations

import asyncio
from pathlib import Path

from app.tools.contracts import ToolResult
from app.tools.path_utils import IGNORED_DIR_NAMES, resolve_path

_MAX_ENTRIES = 1000
_MAX_DEPTH = 4


def _walk_with_depth_and_ignore(
    base: Path, max_depth: int, max_entries: int
) -> list[str]:
    """Recursively list paths under base, respecting depth limit and ignored dirs."""
    items: list[str] = []
    base_resolved = base.resolve()

    truncated = [False]

    def _walk(current: Path, depth: int) -> None:
        if depth > max_depth or truncated[0]:
            return
        try:
            for p in sorted(current.iterdir()):
                if truncated[0]:
                    return
                if len(items) >= max_entries:
                    truncated[0] = True
                    items.append(f"... truncated at {max_entries} entries")
                    return
                if p.name in IGNORED_DIR_NAMES:
                    continue
                items.append(str(p))
                if p.is_dir():
                    _walk(p, depth + 1)
        except OSError:
            pass

    _walk(base_resolved, 0)
    return items


def _list_files_sync(base: Path, recursive: bool) -> list[str]:
    """List files; runs in thread pool."""
    if recursive:
        items = _walk_with_depth_and_ignore(base, _MAX_DEPTH, _MAX_ENTRIES)
    else:
        items = sorted(
            str(p) for p in base.iterdir() if p.name not in IGNORED_DIR_NAMES
        )
    if len(items) > _MAX_ENTRIES:
        items = items[:_MAX_ENTRIES]
        items.append(f"... truncated at {_MAX_ENTRIES} entries")
    return items


class ListFilesTool:
    name = "list_files"
    description = (
        "List files in a directory. path must be an absolute path (e.g. /path/to/project). "
        "Omit to list project root. Recursive listings have a depth limit of 4 levels. "
        "Auto-ignores .venv, node_modules, __pycache__, .git, cache, dist, build, and similar dirs."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "recursive": {
                "type": "boolean",
                "description": "If true, list recursively up to 4 levels deep. Ignores .venv, node_modules, etc.",
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
        path_raw = payload.get("path") or ""
        if not path_raw or path_raw.strip() == ".":
            if not project_root:
                return ToolResult(
                    output="path is required when no project is selected; use an absolute path.",
                    file_edits=[],
                    ok=False,
                )
            path_raw = str(Path(project_root).resolve())
        try:
            base = resolve_path(path_raw.strip(), project_root=project_root)
        except ValueError as exc:
            return ToolResult(output=str(exc), file_edits=[], ok=False)
        if not base.exists() or not base.is_dir():
            return ToolResult(output=f"Directory not found: {base}", file_edits=[], ok=False)

        items = await asyncio.to_thread(
            _list_files_sync, base, bool(payload.get("recursive", False))
        )
        return ToolResult(output="\n".join(items), file_edits=[])
