"""Project overview injection with depth selection based on token budget."""

from __future__ import annotations

from pathlib import Path

from app.services.token_counter import count_text_tokens

PROJECT_OVERVIEW_MAX_DEPTH = 3
PROJECT_OVERVIEW_TOKEN_TARGET = 2000


def _walk_to_depth(
    root: Path,
    *,
    max_depth: int,
    prefix: str = "",
    depth: int = 0,
) -> list[str]:
    """Walk directory up to ``max_depth`` levels and return indented lines."""
    if depth >= max_depth:
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
            sub = _walk_to_depth(p, max_depth=max_depth, prefix=indent, depth=depth + 1)
            lines.extend(sub)
        else:
            lines.append(f"{prefix}{p.name}")
    return lines


def _render_project_overview(
    *,
    root: Path,
    lines: list[str],
    selected_depth: int,
    max_depth: int,
    token_target: int,
    total_entries: int | None = None,
) -> str:
    root_str = str(root)
    heading = f"Project structure (selected depth: {selected_depth}/{max_depth}, token target: {token_target}):"
    tail = ""
    if isinstance(total_entries, int) and total_entries > len(lines):
        heading = (
            "Project structure "
            f"(selected depth: {selected_depth}/{max_depth}, token target: {token_target}, "
            f"entries: {len(lines)}/{total_entries}):"
        )
        omitted = total_entries - len(lines)
        tail = (
            "\n\n"
            f"... ({omitted} additional entries omitted to stay near token target)"
        )
    return (
        f"Project root (absolute path): {root_str}\n\n"
        f"All paths in tool calls (read_file, edit_file, list_files, execute_command cwd) must be absolute paths under this root (e.g. {root_str}/src/main.py). Never use relative paths.\n\n"
        + heading
        + "\n\n"
        + "\n".join(lines)
        + tail
    )


def _fit_lines_to_target(
    *,
    root: Path,
    lines: list[str],
    selected_depth: int,
    max_depth: int,
    token_target: int,
    model: str | None,
) -> str:
    """Pick the smallest prefix of lines whose rendered overview reaches token_target."""
    low = 1
    high = len(lines)
    best: str | None = None
    best_len: int | None = None

    while low <= high:
        mid = (low + high) // 2
        candidate = _render_project_overview(
            root=root,
            lines=lines[:mid],
            selected_depth=selected_depth,
            max_depth=max_depth,
            token_target=token_target,
            total_entries=len(lines),
        )
        tokens = count_text_tokens(candidate, model=model)
        if tokens >= token_target:
            best = candidate
            best_len = mid
            high = mid - 1
        else:
            low = mid + 1

    if best is not None:
        return best

    return _render_project_overview(
        root=root,
        lines=lines if best_len is None else lines[:best_len],
        selected_depth=selected_depth,
        max_depth=max_depth,
        token_target=token_target,
    )


def build_project_overview_text(
    project_path: str | None,
    *,
    model: str | None = None,
    max_depth: int = PROJECT_OVERVIEW_MAX_DEPTH,
    token_target: int = PROJECT_OVERVIEW_TOKEN_TARGET,
) -> str | None:
    """Build project overview text with dynamic depth selection, or return None."""
    if not project_path:
        return None
    root = Path(project_path).resolve()
    if not root.exists() or not root.is_dir():
        return None
    max_depth = max(1, int(max_depth))
    token_target = max(1, int(token_target))

    selected_lines: list[str] = []
    selected_overview = ""

    for depth in range(1, max_depth + 1):
        lines = _walk_to_depth(root, max_depth=depth)
        if not lines:
            continue
        overview = _render_project_overview(
            root=root,
            lines=lines,
            selected_depth=depth,
            max_depth=max_depth,
            token_target=token_target,
        )
        selected_lines = lines
        selected_overview = overview
        if count_text_tokens(overview, model=model) >= token_target:
            selected_overview = _fit_lines_to_target(
                root=root,
                lines=lines,
                selected_depth=depth,
                max_depth=max_depth,
                token_target=token_target,
                model=model,
            )
            break

    if not selected_lines:
        return None
    return selected_overview


def build_project_overview_system_message(
    project_path: str | None,
    *,
    model: str | None = None,
    max_depth: int = PROJECT_OVERVIEW_MAX_DEPTH,
    token_target: int = PROJECT_OVERVIEW_TOKEN_TARGET,
) -> dict | None:
    """Build the project overview system message dict, or return None."""
    overview = build_project_overview_text(
        project_path,
        model=model,
        max_depth=max_depth,
        token_target=token_target,
    )
    if not overview:
        return None
    return {"role": "system", "content": overview}


def add_project_overview_3_levels(
    messages: list[dict],
    project_path: str | None = None,
    *,
    model: str | None = None,
    max_depth: int = PROJECT_OVERVIEW_MAX_DEPTH,
    token_target: int = PROJECT_OVERVIEW_TOKEN_TARGET,
) -> list[dict]:
    """
    Prepend a system message with project directory overview.

    Depth selection is dynamic:
    - expand one level at a time starting from depth 1
    - stop at the first depth whose overview reaches ``token_target`` tokens
    - otherwise use the full configured ``max_depth``

    Args:
        messages: Chat messages (copied, not mutated).
        project_path: Path to project root. If None or invalid, returns messages unchanged.
        model: Optional model id for tokenizer selection.
        max_depth: Maximum directory depth to include.
        token_target: Token target for overview sizing.

    Returns:
        New message list with overview inserted after the first system message, or at start.
    """
    block = build_project_overview_system_message(
        project_path,
        model=model,
        max_depth=max_depth,
        token_target=token_target,
    )
    if not block:
        return list(messages)
    result = list(messages)
    insert_at = 0
    for i, m in enumerate(result):
        if m.get("role") == "system":
            insert_at = i + 1
        else:
            break
    result.insert(insert_at, block)
    return result
