"""Path resolution utilities for tools operating within a project root."""

from __future__ import annotations

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


def resolve_path(
    raw_path: str,
    *,
    project_root: str | None = None,
) -> Path:
    """
    Resolve an absolute path with security checks. Only absolute paths accepted.

    Args:
        raw_path: User-provided path; must be absolute.
        project_root: Project root directory. If provided, path must be within
            it. Used to validate access scope.

    Returns:
        Resolved absolute Path. Raises ValueError if path is restricted or
        not absolute.
    """
    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        raise ValueError(
            "Path must be absolute. Use the project root path from the project "
            "overview (e.g. /path/to/project/src/file.py)."
        )
    target = target.resolve()
    for prefix in _BLOCKED_PREFIXES:
        if str(target).startswith(prefix):
            raise ValueError(f"Access denied: {raw_path} is in a restricted directory")
    try:
        target.relative_to(get_tool_outputs_root())
    except ValueError:
        pass
    else:
        return target
    if project_root:
        base = Path(project_root).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            raise ValueError(
                f"Path {raw_path} is outside the project root. "
                f"Only paths under {base} are allowed."
            )
    return target
