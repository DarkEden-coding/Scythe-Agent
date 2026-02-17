"""Path resolution utilities for tools operating within a project root."""

from __future__ import annotations

from pathlib import Path

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
    Resolve a path relative to the project root, with security checks.

    Args:
        raw_path: User-provided path (relative or absolute).
        project_root: Project root directory. If provided, relative paths are
            resolved against it. If None, paths resolve against CWD.

    Returns:
        Resolved absolute Path. Raises ValueError if path is restricted.
    """
    base = Path(project_root).resolve() if project_root else Path.cwd()
    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        target = (base / target).resolve()
    else:
        target = target.resolve()
    for prefix in _BLOCKED_PREFIXES:
        if str(target).startswith(prefix):
            raise ValueError(f"Access denied: {raw_path} is in a restricted directory")
    return target
