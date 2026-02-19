"""Grep search tool using ripgrep (rg)."""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

from app.tools.contracts import ToolResult
from app.tools.path_utils import IGNORED_DIR_NAMES, resolve_path


def _resolve_search_path(
    path_raw: str, project_root: str | None
) -> tuple[Path | None, str | None]:
    """Resolve search directory. Returns (path, error_message)."""
    if not path_raw or path_raw.strip() == ".":
        if not project_root:
            return None, "path is required when no project is selected; use an absolute path."
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


def _build_rg_args(payload: dict, pattern: str, base: Path) -> list[str]:
    """Build ripgrep command args."""
    args = ["rg", "--no-heading", "--line-number"]
    for name in IGNORED_DIR_NAMES:
        args.extend(["--glob", f"!**/{name}/**"])
    if payload.get("case_insensitive"):
        args.append("--ignore-case")
    if payload.get("files_only"):
        args.append("--files-with-matches")
    if type_filter := str(payload.get("type", "")).strip():
        args.extend(["--type", type_filter])
    args.extend(["--", pattern, str(base)])
    return args


def _format_grouped(output: str) -> str:
    """Reformat ripgrep path:line:content lines into file-grouped format for token efficiency."""
    if not output:
        return output
    grouped: dict[str, list[tuple[int, str]]] = {}
    for line in output.split("\n"):
        m = re.match(r"^(.+):(\d+):(.*)$", line)
        if m:
            path, num, content = m.group(1), int(m.group(2)), m.group(3)
            grouped.setdefault(path, []).append((num, content.strip()))
    parts = []
    for path, hits in grouped.items():
        parts.append(f"{path}:")
        for num, content in hits:
            parts.append(f"  {num}: {content}")
        parts.append("")
    return "\n".join(parts).strip()


def _interpret_grep_result(
    returncode: int,
    stdout: bytes,
    stderr: bytes,
    *,
    files_only: bool = False,
) -> str:
    """Convert ripgrep subprocess result to output string."""
    out = (stdout or b"").decode("utf-8", errors="replace").strip()
    err_text = (stderr or b"").decode("utf-8", errors="replace").strip()
    if returncode == 1 and not out:
        return "No matches found" + (f"\n{err_text}" if err_text else "")
    if returncode != 0 and err_text:
        return f"Grep error: {err_text}"
    if not out:
        return "(no output)"
    if files_only:
        return out
    return _format_grouped(out)


class GrepTool:
    name = "grep"
    description = (
        "Search for a pattern in files using ripgrep. "
        "path must be absolute when provided (file or directory). "
        "Omit path to search project root. Supports regex patterns. "
        "Auto-ignores .venv, node_modules, __pycache__, .git, cache, dist, build, and similar dirs. "
        "Output format (grouped by file):\n"
        "  path/to/file.py:\n"
        "    42: line content here\n"
        "    99: another match"
    )
    input_schema = {
        "type": "object",
        "required": ["pattern"],
        "properties": {
            "pattern": {"type": "string", "description": "Search pattern (regex)"},
            "path": {"type": "string", "description": "File or directory to search in"},
            "case_insensitive": {"type": "boolean", "description": "Ignore case", "default": False},
            "type": {"type": "string", "description": "File type filter (e.g. py, ts, js)"},
            "files_only": {"type": "boolean", "description": "Only return matching file paths", "default": False},
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
        if shutil.which("rg") is None:
            return ToolResult(
                output="ripgrep (rg) is not installed. Install it to use the grep tool.",
                file_edits=[],
                ok=False,
            )

        pattern = str(payload.get("pattern", "")).strip()
        if not pattern:
            return ToolResult(output="Missing pattern", file_edits=[], ok=False)

        base, err = _resolve_search_path(
            payload.get("path") or "", project_root
        )
        if err or base is None:
            return ToolResult(output=err or "Invalid path", file_edits=[], ok=False)

        args = _build_rg_args(payload, pattern, base)
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        except asyncio.TimeoutError:
            return ToolResult(output="Grep timed out after 60s", file_edits=[], ok=False)
        except Exception as exc:
            return ToolResult(output=f"Grep failed: {exc}", file_edits=[], ok=False)

        output = _interpret_grep_result(
            proc.returncode if proc.returncode is not None else 1,
            stdout or b"",
            stderr or b"",
            files_only=payload.get("files_only", False),
        )
        return ToolResult(output=output, file_edits=[])
