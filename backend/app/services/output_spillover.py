"""Spill large tool outputs to disk; use token-based thresholds."""

from __future__ import annotations

import logging
import uuid

from app.services.token_counter import count_text_tokens
from app.tools.path_utils import get_tool_outputs_root

logger = logging.getLogger(__name__)

TOOL_OUTPUT_TOKEN_THRESHOLD = 2000
PREVIEW_LINES = 50


def spill_tool_output(
    output: str,
    project_id: str,
    *,
    max_tokens: int = TOOL_OUTPUT_TOKEN_THRESHOLD,
    model: str | None = None,
) -> tuple[str, str | None, int | None]:
    """
    If output exceeds token threshold, spill to temp file and return preview.

    Returns:
        (preview_content, abs_file_path | None, total_lines | None).
        If no spill, path and total_lines are None.
    """
    tokens = count_text_tokens(output, model=model)
    if tokens <= max_tokens:
        return output, None, None

    lines = output.splitlines()
    base_dir = get_tool_outputs_root() / "projects" / project_id
    output_uuid = uuid.uuid4().hex
    out_path = base_dir / f"{output_uuid}.txt"

    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to spill tool output to %s: %s", out_path, exc)
        return output, None, None

    total = len(lines)
    first = "\n".join(lines[:PREVIEW_LINES])
    last = "\n".join(lines[-PREVIEW_LINES:])
    abs_path = str(out_path.resolve())
    preview = f"""{first}

... [truncated; {total} lines total] ...

{last}"""
    instruction = (
        f"The preceding tool output was truncated ({total} lines). "
        f"Full output saved to: {abs_path}. "
        f"Use read_file to read sections as needed."
    )
    return f"{preview}\n\n{instruction}", abs_path, total


def preview_tool_output_if_over_threshold(
    content: str,
    token_count: int,
    *,
    max_tokens: int = TOOL_OUTPUT_TOKEN_THRESHOLD,
) -> str:
    """Return first+last PREVIEW_LINES when content exceeds token threshold."""
    if token_count <= max_tokens:
        return content
    lines = content.splitlines()
    total = len(lines)
    first = "\n".join(lines[:PREVIEW_LINES])
    last = "\n".join(lines[-PREVIEW_LINES:])
    return f"{first}\n\n... [truncated; {total} lines total] ...\n\n{last}"
