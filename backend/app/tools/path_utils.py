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
    if project_root:
        base = Path(project_root).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            raise ValueError(
                f"Path {raw_path} is outside the project root. "
                f"Only paths under {base} are allowed."
            )
    for prefix in _BLOCKED_PREFIXES:
        if str(target).startswith(prefix):
            raise ValueError(f"Access denied: {raw_path} is in a restricted directory")
    return target
