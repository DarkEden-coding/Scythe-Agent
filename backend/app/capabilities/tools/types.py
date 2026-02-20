from __future__ import annotations

from dataclasses import dataclass, field

from app.tools.contracts import ToolFileEdit


@dataclass
class ToolArtifact:
    artifact_type: str
    file_path: str
    line_count: int | None = None
    preview_lines: int | None = None


@dataclass
class ToolExecutionResult:
    """Canonical tool execution result for capability plugins."""

    output: str
    output_preview: str | None = None
    artifacts: list[ToolArtifact] = field(default_factory=list)
    file_edits: list[ToolFileEdit] = field(default_factory=list)
    ok: bool = True
    error: str | None = None
