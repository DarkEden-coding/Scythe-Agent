"""Spill large tool outputs to disk and return summarized content for the agent."""

from __future__ import annotations

import logging
import uuid

from app.tools.path_utils import get_tool_outputs_root

logger = logging.getLogger(__name__)

LARGE_OUTPUT_LINE_THRESHOLD = 1000
PREVIEW_LINES = 50


def maybe_spill(output: str, project_id: str) -> tuple[str, str | None]:
    """
    If output exceeds threshold lines, spill to file and return summarized content.

    Returns:
        (content_for_agent, full_file_path | None). If no spill, path is None.
    """
    lines = output.splitlines()
    if len(lines) <= LARGE_OUTPUT_LINE_THRESHOLD:
        return output, None

    base_dir = get_tool_outputs_root() / "projects" / project_id
    output_uuid = uuid.uuid4().hex
    out_path = base_dir / f"{output_uuid}.txt"

    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to spill tool output to %s: %s", out_path, exc)
        return output, None

    total = len(lines)
    first = "\n".join(lines[:PREVIEW_LINES])
    last = "\n".join(lines[-PREVIEW_LINES:])
    abs_path = str(out_path.resolve())

    summarized = f"""You are being shown the first {PREVIEW_LINES} and last {PREVIEW_LINES} lines of this output ({total} lines total). Full output saved to: {abs_path}

{first}

... [truncated] ...

{last}

---
Recommended: Use the grep search tool on the file first to locate relevant sections, then use the read_file tool with start and end (1-based line numbers) to read those sections."""

    return summarized, abs_path
