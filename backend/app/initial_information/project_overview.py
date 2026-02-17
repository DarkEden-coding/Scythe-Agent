"""Project overview: 3-level directory structure for context."""

from __future__ import annotations

from pathlib import Path


def _walk_3_levels(root: Path, prefix: str = "", depth: int = 0) -> list[str]:
    """Walk directory up to 3 levels, return indented lines."""
    if depth >= 3:
        return []
    lines: list[str] = []
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return [f"{prefix}(error reading directory)"]
    for p in entries:
        if p.name.startswith(".") and depth == 0:
            continue
        indent = "  " * (depth + 1)
        if p.is_dir():
            lines.append(f"{prefix}{p.name}/")
            sub = _walk_3_levels(p, prefix=indent, depth=depth + 1)
            lines.extend(sub)
        else:
            lines.append(f"{prefix}{p.name}")
    return lines


def add_project_overview_3_levels(
    messages: list[dict],
    project_path: str | None = None,
) -> list[dict]:
    """
    Prepend a system message with 3-level project directory overview.

    Args:
        messages: Chat messages (copied, not mutated).
        project_path: Path to project root. If None or invalid, returns messages unchanged.

    Returns:
        New message list with overview inserted after the first system message, or at start.
    """
    if not project_path:
        return list(messages)
    root = Path(project_path).resolve()
    if not root.exists() or not root.is_dir():
        return list(messages)
    lines = _walk_3_levels(root)
    if not lines:
        return list(messages)
    root_str = str(root)
    overview = (
        f"Project root: {root_str}\n\n"
        "All file paths in tool calls (read_file, edit_file, list_files, execute_command cwd) must be relative to this root.\n\n"
        "Project structure (first 3 directory levels):\n\n" + "\n".join(lines)
    )
    block = {"role": "system", "content": overview}
    result = list(messages)
    insert_at = 0
    for i, m in enumerate(result):
        if m.get("role") == "system":
            insert_at = i + 1
        else:
            break
    result.insert(insert_at, block)
    return result
