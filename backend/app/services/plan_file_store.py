"""Storage helper for planning markdown files."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path


_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


class PlanFileStore:
    def __init__(self, backend_root: Path | None = None) -> None:
        if backend_root is None:
            backend_root = Path(__file__).resolve().parent.parent
        self._root = backend_root / "project_plans"

    @property
    def root(self) -> Path:
        return self._root

    def _safe_segment(self, raw: str, *, label: str) -> str:
        value = str(raw or "").strip()
        if not value or not _SAFE_SEGMENT.fullmatch(value):
            raise ValueError(f"Invalid {label}: {raw}")
        return value

    def plan_path(self, *, project_id: str, plan_id: str) -> Path:
        safe_project = self._safe_segment(project_id, label="project_id")
        safe_plan = self._safe_segment(plan_id, label="plan_id")
        return self._root / safe_project / "plans" / f"{safe_plan}.md"

    @staticmethod
    def sha256_text(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def read_plan(self, *, project_id: str, plan_id: str) -> tuple[str, Path]:
        path = self.plan_path(project_id=project_id, plan_id=plan_id)
        if not path.exists():
            raise ValueError(f"Plan file does not exist: {path}")
        return path.read_text(encoding="utf-8"), path

    def write_plan(self, *, project_id: str, plan_id: str, content: str) -> tuple[Path, str]:
        path = self.plan_path(project_id=project_id, plan_id=plan_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                tmp_file.write(content)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return path, self.sha256_text(content)
