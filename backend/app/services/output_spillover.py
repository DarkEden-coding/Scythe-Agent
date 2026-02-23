"""Spill large tool outputs to disk; use token-based thresholds."""

from __future__ import annotations

import logging
import uuid

from app.services.token_counter import count_text_tokens, extract_preview_by_tokens
from app.tools.path_utils import get_tool_outputs_root

logger = logging.getLogger(__name__)

TOOL_OUTPUT_TOKEN_THRESHOLD = 2000
PREVIEW_TOKENS = 500


def spill_tool_output(
    output: str,
    project_id: str,
    *,
    max_tokens: int = TOOL_OUTPUT_TOKEN_THRESHOLD,
    preview_tokens: int = PREVIEW_TOKENS,
    model: str | None = None,
) -> tuple[str, str | None, int | None]:
    """
    If output exceeds token threshold, spill to temp file and return preview.

    Returns:
        (preview_content, abs_file_path | None, total_tokens | None).
        If no spill, path and total_tokens are None.
    """
    tokens = count_text_tokens(output, model=model)
    if tokens <= max_tokens:
        return output, None, None

    base_dir = get_tool_outputs_root() / "projects" / project_id
    output_uuid = uuid.uuid4().hex
    out_path = base_dir / f"{output_uuid}.txt"

    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to spill tool output to %s: %s", out_path, exc)
        return output, None, None

    preview_content = extract_preview_by_tokens(output, preview_tokens, model=model)
    abs_path = str(out_path.resolve())
    instruction = (
        f"The preceding tool output was truncated ({tokens} tokens). "
        f"Full output saved to: {abs_path}. "
        f"Use read_file to read sections as needed."
    )
    return f"{preview_content}\n\n{instruction}", abs_path, tokens


def preview_tool_output_if_over_threshold(
    content: str,
    token_count: int,
    *,
    max_tokens: int = TOOL_OUTPUT_TOKEN_THRESHOLD,
    preview_tokens: int = PREVIEW_TOKENS,
    model: str | None = None,
) -> str:
    """Return first+last preview_tokens when content exceeds token threshold."""
    if token_count <= max_tokens:
        return content
    return extract_preview_by_tokens(content, preview_tokens, model=model)
