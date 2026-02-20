"""Artifact store for large tool outputs and future execution artifacts."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.tools.path_utils import get_tool_outputs_root

logger = logging.getLogger(__name__)


@dataclass
class ArtifactRecord:
    artifact_type: str
    file_path: str
    line_count: int | None = None
    preview_lines: int | None = None


class ArtifactStore:
    def __init__(
        self,
        *,
        large_output_line_threshold: int = 1000,
        preview_lines: int = 50,
    ) -> None:
        self._large_output_line_threshold = large_output_line_threshold
        self._preview_lines = preview_lines

    def materialize_tool_output(
        self,
        output: str,
        *,
        project_id: str,
    ) -> tuple[str, list[ArtifactRecord]]:
        """Return output preview and persisted artifacts for oversized output."""
        lines = output.splitlines()
        if len(lines) <= self._large_output_line_threshold:
            return output, []

        base_dir = get_tool_outputs_root() / "projects" / project_id
        output_uuid = uuid.uuid4().hex
        out_path = base_dir / f"{output_uuid}.txt"

        try:
            base_dir.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output, encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to persist artifact to %s: %s", out_path, exc)
            return output, []

        total = len(lines)
        first = "\n".join(lines[: self._preview_lines])
        last = "\n".join(lines[-self._preview_lines :])
        preview = f"""{first}

... [truncated; {total} lines total] ...

{last}"""

        artifacts = [
            ArtifactRecord(
                artifact_type="tool_output",
                file_path=str(out_path.resolve()),
                line_count=total,
                preview_lines=self._preview_lines,
            )
        ]
        return preview, artifacts

    def delete_path(self, path: str) -> None:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            logger.debug("Failed to delete artifact path=%s", path, exc_info=True)

    def cleanup_project(self, project_id: str) -> None:
        base_dir = get_tool_outputs_root() / "projects" / project_id
        if not base_dir.exists():
            return
        for child in base_dir.iterdir():
            if child.is_file():
                self.delete_path(str(child))
