"""Artifact store for large tool outputs and future execution artifacts."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.services.output_spillover import (
    PREVIEW_LINES,
    TOOL_OUTPUT_TOKEN_THRESHOLD,
    spill_tool_output,
)
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
        token_threshold: int = TOOL_OUTPUT_TOKEN_THRESHOLD,
    ) -> None:
        self._token_threshold = token_threshold

    def materialize_tool_output(
        self,
        output: str,
        *,
        project_id: str,
        model: str | None = None,
    ) -> tuple[str, list[ArtifactRecord]]:
        """Return output preview and persisted artifacts when over token threshold."""
        preview, file_path, total_lines = spill_tool_output(
            output,
            project_id,
            max_tokens=self._token_threshold,
            model=model,
        )
        if file_path is None:
            return output, []
        artifacts = [
            ArtifactRecord(
                artifact_type="tool_output",
                file_path=file_path,
                line_count=total_lines,
                preview_lines=PREVIEW_LINES,
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
