"""Path resolution utilities for tools operating within a project root."""

from __future__ import annotations

import re
from pathlib import Path

# backend/app/tools/ -> backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
TOOL_OUTPUTS_ROOT = _BACKEND_ROOT / "tool_outputs"


def get_tool_outputs_root() -> Path:
    """Return the directory for spilled tool outputs (backend/tool_outputs)."""
    return TOOL_OUTPUTS_ROOT


# Directory names to auto-ignore in grep and list_files (e.g. .venv, node_modules)
IGNORED_DIR_NAMES = frozenset({
    ".venv", "venv", ".env", "node_modules", "__pycache__",
    ".git", ".hg", ".svn", ".cache", "cache",
    "dist", "build", ".next", ".nuxt", ".output",
    "coverage", ".coverage", ".pytest_cache", ".mypy_cache",
    "target",  # Rust
    ".tox", ".eggs",
})

_BLOCKED_PREFIXES = [
    "/etc",
    "/var",
    "/usr",
    "/bin",
    "/sbin",
    "/boot",
    "/proc",
    "/sys",
    "/dev",
]

# Some providers occasionally stream argument fragments with trailing JSON
# delimiters (e.g. `/path/File.java}},`). Strip only clearly synthetic suffixes.
_TRAILING_DELIMITER_CLUSTER = re.compile(r"^(?P<core>.+?)(?P<noise>[{}\[\],]+)$")

# Agent/LLM output often appends quote+brace (e.g. path'}, path`} from markdown/code).
# Only strip when a quote char is present so we preserve legitimate names like "data}".
_TRAILING_QUOTE_DELIMITER = re.compile(
    r"^(?P<path>.+?)(?P<noise>['\"`][}\[\],]*|[}\[\],]*['\"`][}\[\],]*)$"
)


def sanitize_raw_path(raw_path: str) -> str:
    """Normalize path text from tool payloads before security checks."""
    value = str(raw_path or "").strip()
    if not value:
        return value

    # Drop simple wrappers often introduced by quoting/formatting.
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'", "`"}:
        value = value[1:-1].strip()
    else:
        # Strip trailing quote+delimiter (e.g. path'}, path`}) before rstrip.
        match = _TRAILING_QUOTE_DELIMITER.match(value)
        if match:
            core = match.group("path").rstrip()
            if core:
                value = core
        value = value.rstrip(' \t\r\n,;"\'`')
        if value and value[0] in {'"', "'", "`"}:
            value = value[1:].lstrip()

    match = _TRAILING_DELIMITER_CLUSTER.match(value)
    if match:
        noise = match.group("noise")
        # Keep single trailing braces (valid on POSIX). Trim only multi-char clusters.
        if len(noise) >= 2:
            core = match.group("core").rstrip()
            if core:
                value = core
    return value


def resolve_path(
    raw_path: str,
    *,
    project_root: str | None = None,
    allow_external: bool = False,
) -> Path:
    """
    Resolve an absolute path with security checks. Only absolute paths accepted.

    Args:
        raw_path: User-provided path; must be absolute.
        project_root: Project root directory. If provided and allow_external is
            False, path must be within it or under tool_outputs.
        allow_external: If True (e.g. for read_file), allow any path outside
            project_root. Tool output paths and blocked prefixes still apply.

    Returns:
        Resolved absolute Path. Raises ValueError if path is restricted or
        not absolute.
    """
    normalized_path = sanitize_raw_path(raw_path)
    target = Path(normalized_path).expanduser()
    if not target.is_absolute():
        raise ValueError(
            "Path must be absolute. Use the project root path from the project "
            "overview (e.g. /path/to/project/src/file.py)."
        )
    target = target.resolve()
    for prefix in _BLOCKED_PREFIXES:
        if str(target).startswith(prefix):
            raise ValueError(
                f"Access denied: {normalized_path} is in a restricted directory"
            )
    try:
        target.relative_to(get_tool_outputs_root())
    except ValueError:
        pass
    else:
        return target
    if allow_external:
        return target
    if project_root:
        base = Path(project_root).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            raise ValueError(
                f"Path {normalized_path} is outside the project root. "
                f"Only paths under {base} are allowed."
            )
    return target
