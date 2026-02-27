"""Grep search tool using ripgrep-python."""

from __future__ import annotations

import asyncio
import importlib
import re
from pathlib import Path
from typing import Any

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.types import ToolExecutionResult
from app.tools.path_utils import IGNORED_DIR_NAMES, resolve_path


def _load_pyripgrep_grep() -> type[Any] | None:
    """Load `pyripgrep.Grep` dynamically to avoid hard import failure at module import time."""
    try:
        module = importlib.import_module("pyripgrep")
        grep_cls = getattr(module, "Grep", None)
        if isinstance(grep_cls, type):
            return grep_cls
    except Exception:
        pass
    return None


PYRIPGREP_GREP = _load_pyripgrep_grep()


def _resolve_search_path(
    path_raw: str, project_root: str | None
) -> tuple[Path | None, str | None]:
    """Resolve search directory. Returns (path, error_message)."""
    if not path_raw or path_raw.strip() == ".":
        if not project_root:
            return (
                None,
                "path is required when no project is selected; use an absolute path.",
            )
        path_raw = str(Path(project_root).resolve())
    try:
        base = resolve_path(path_raw.strip(), project_root=project_root)
    except ValueError as exc:
        return None, str(exc)
    if not base.exists():
        return None, f"Path not found: {base}"
    if not base.is_dir() and not base.is_file():
        return None, f"Path is neither a file nor directory: {base}"
    return base, None


def _format_grouped_text(output: str) -> str:
    """Reformat `path:line:content` text into grouped output."""
    if not output:
        return output
    grouped: dict[str, list[tuple[int, str]]] = {}
    for line in output.split("\n"):
        m = re.match(r"^(.+):(\d+):(.*)$", line)
        if m:
            path, num, content = m.group(1), int(m.group(2)), m.group(3)
            grouped.setdefault(path, []).append((num, content.strip()))
    if not grouped:
        return "(no output)"
    parts = []
    for path, hits in grouped.items():
        parts.append(f"{path}:")
        for num, content in hits:
            parts.append(f"  {num}: {content}")
        parts.append("")
    return "\n".join(parts).strip()


def _search_with_pyripgrep(payload: dict, pattern: str, base: Path) -> list[str]:
    """Execute search using ripgrep-python (pyripgrep) bindings."""
    if PYRIPGREP_GREP is None:
        raise ImportError("pyripgrep is not installed")

    grep = PYRIPGREP_GREP()
    glob = None
    if type_filter := str(payload.get("type", "")).strip():
        ext = type_filter.lstrip(".")
        glob = f"*.{ext}"

    output_mode = "files_with_matches" if payload.get("files_only") else "content"

    return list(
        grep.search(
            pattern,
            path=str(base),
            glob=glob,
            output_mode=output_mode,
            n=True,
            i=bool(payload.get("case_insensitive")),
        )
    )


def _filter_ignored_paths(lines: list[str]) -> list[str]:
    """Filter out ignored directory matches from returned lines/paths."""
    cleaned: list[str] = []
    ignored_markers = tuple(f"\\{name}\\" for name in IGNORED_DIR_NAMES) + tuple(
        f"/{name}/" for name in IGNORED_DIR_NAMES
    )
    for line in lines:
        text = line.replace("/", "\\")
        if any(marker in text for marker in ignored_markers):
            continue
        cleaned.append(line)
    return cleaned


def _interpret_pyripgrep_result(lines: list[str], *, files_only: bool = False) -> str:
    """Normalize ripgrep-python output into grep tool output format."""
    if not lines:
        return "No matches found"

    if files_only:
        seen: set[str] = set()
        out: list[str] = []
        for line in lines:
            m = re.match(r"^(.+?):\d+:", line)
            path = m.group(1) if m else line
            if path not in seen:
                seen.add(path)
                out.append(path)
        return "\n".join(out) if out else "No matches found"

    joined = "\n".join(lines)
    if re.search(r"^.+:\d+:", joined, flags=re.MULTILINE):
        return _format_grouped_text(joined)
    return "\n".join(lines)


async def _handler(payload: dict, context: ToolExecutionContext) -> ToolExecutionResult:
    pattern = str(payload.get("pattern", "")).strip()
    if not pattern:
        return ToolExecutionResult(output="Missing pattern", file_edits=[], ok=False)

    base, err = _resolve_search_path(payload.get("path") or "", context.project_root)
    if err or base is None:
        return ToolExecutionResult(
            output=err or "Invalid path", file_edits=[], ok=False
        )

    try:
        lines = await asyncio.wait_for(
            asyncio.to_thread(_search_with_pyripgrep, payload, pattern, base),
            timeout=60,
        )
        lines = _filter_ignored_paths(lines)
        output = _interpret_pyripgrep_result(
            lines,
            files_only=bool(payload.get("files_only", False)),
        )
        return ToolExecutionResult(output=output, file_edits=[])
    except ImportError:
        return ToolExecutionResult(
            output="ripgrep-python is not installed. Install it to use the grep tool.",
            file_edits=[],
            ok=False,
        )
    except asyncio.TimeoutError:
        return ToolExecutionResult(
            output="Grep timed out after 60s", file_edits=[], ok=False
        )
    except Exception as exc:
        return ToolExecutionResult(
            output=f"Grep failed: {exc}", file_edits=[], ok=False
        )


TOOL_PLUGIN = ToolPlugin(
    name="grep",
    description=(
        "Search for a pattern in files using ripgrep-python. "
        "path must be absolute when provided (file or directory). "
        "Omit path to search project root. Supports regex patterns. "
        "Auto-ignores .venv, node_modules, __pycache__, .git, cache, dist, build, and similar dirs. "
        "Output format (grouped by file):\n"
        "  path/to/file.py:\n"
        "    42: line content here\n"
        "    99: another match"
    ),
    input_schema={
        "type": "object",
        "required": ["pattern"],
        "properties": {
            "pattern": {"type": "string", "description": "Search pattern (regex)"},
            "path": {"type": "string", "description": "File or directory to search in"},
            "case_insensitive": {
                "type": "boolean",
                "description": "Ignore case",
                "default": False,
            },
            "type": {
                "type": "string",
                "description": "File type filter (e.g. py, ts, js)",
            },
            "files_only": {
                "type": "boolean",
                "description": "Only return matching file paths",
                "default": False,
            },
        },
    },
    approval_policy="rules",
    handler=_handler,
)
