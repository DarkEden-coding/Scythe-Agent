from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.project_memory import ProjectMemory
from app.db.repositories.project_memory_repo import ProjectMemoryRepository
from app.db.repositories.project_repo import ProjectRepository
from app.schemas.projects import (
    DeleteProjectMemoryResponse,
    GetProjectMemoriesResponse,
    ProjectMemoryOut,
    UpsertProjectMemoryRequest,
    UpsertProjectMemoryResponse,
)
from app.utils.ids import generate_id
from app.utils.time import utc_now_iso


class ProjectMemoryService:
    TITLE_MAX_LENGTH = 120
    CONTENT_MAX_LENGTH = 2_000
    CONTENT_MIN_LENGTH = 1
    CODE_FENCE_MARKERS = ("```", "~~~")

    def __init__(self, db: Session):
        self.repo = ProjectMemoryRepository(db)
        self.project_repo = ProjectRepository(db)

    @staticmethod
    def _now() -> str:
        return utc_now_iso()

    def _ensure_project(self, project_id: str) -> None:
        if self.project_repo.get_project(project_id) is None:
            raise ValueError(f"Project not found: {project_id}")

    def _normalize_title(self, title: str) -> str:
        normalized = " ".join((title or "").split()).strip()
        if not normalized:
            raise ValueError("Memory title is required")
        if len(normalized) > self.TITLE_MAX_LENGTH:
            raise ValueError(f"Memory title must be <= {self.TITLE_MAX_LENGTH} characters")
        return normalized

    def _normalize_content(self, content_markdown: str) -> str:
        content = (content_markdown or "").strip()
        if len(content) < self.CONTENT_MIN_LENGTH:
            raise ValueError("Memory content is required")
        if len(content) > self.CONTENT_MAX_LENGTH:
            raise ValueError(
                "Memory content is too large; keep it minimal and preference-focused"
            )
        if any(marker in content for marker in self.CODE_FENCE_MARKERS):
            raise ValueError("Do not store code blocks in project memories")
        if content.count("\n") > 30:
            raise ValueError("Memory content is too large; avoid long notes or dumps")
        lowered = content.lower()
        blocked_fragments = [
            "stack trace",
            "full file",
            "entire file",
            "code dump",
            "retrieved context",
            "project plan",
        ]
        if any(fragment in lowered for fragment in blocked_fragments):
            raise ValueError(
                "Project memories are only for durable user corrections/preferences, not project data or dumps"
            )
        return content

    def _memory_out(self, memory: ProjectMemory) -> ProjectMemoryOut:
        return ProjectMemoryOut(
            id=memory.id,
            projectId=memory.project_id,
            title=memory.title,
            contentMarkdown=memory.content_markdown,
            createdAt=memory.created_at,
            updatedAt=memory.updated_at,
        )

    def list_project_memories(self, *, project_id: str) -> GetProjectMemoriesResponse:
        self._ensure_project(project_id)
        memories = [
            self._memory_out(memory)
            for memory in self.repo.list_project_memories(project_id)
        ]
        return GetProjectMemoriesResponse(memories=memories)

    def upsert_project_memory(
        self,
        *,
        project_id: str,
        title: str,
        content_markdown: str,
    ) -> UpsertProjectMemoryResponse:
        self._ensure_project(project_id)
        normalized_title = self._normalize_title(title)
        normalized_content = self._normalize_content(content_markdown)
        now = self._now()
        existing = self.repo.get_project_memory_by_title(project_id, normalized_title)
        if existing is None:
            existing = ProjectMemory(
                id=generate_id("pmem"),
                project_id=project_id,
                title=normalized_title,
                content_markdown=normalized_content,
                created_at=now,
                updated_at=now,
            )
            self.repo.create_project_memory(existing)
        else:
            existing.content_markdown = normalized_content
            existing.updated_at = now
        self.repo.commit()
        return UpsertProjectMemoryResponse(memory=self._memory_out(existing))

    def delete_project_memory(self, *, project_id: str, title: str) -> DeleteProjectMemoryResponse:
        self._ensure_project(project_id)
        normalized_title = self._normalize_title(title)
        memory = self.repo.get_project_memory_by_title(project_id, normalized_title)
        if memory is None:
            raise ValueError(f"Project memory not found: {normalized_title}")
        self.repo.delete_project_memory(memory)
        self.repo.commit()
        return DeleteProjectMemoryResponse(deletedTitle=normalized_title)

    def read_memory_titles(self, *, project_id: str) -> list[str]:
        self._ensure_project(project_id)
        return [memory.title for memory in self.repo.list_project_memories(project_id)]

    def read_memories(self, *, project_id: str, titles: list[str] | None = None) -> list[ProjectMemoryOut]:
        self._ensure_project(project_id)
        if titles:
            requested = [self._normalize_title(title) for title in titles]
            rows = self.repo.get_project_memories_by_titles(project_id, requested)
            by_title = {row.title: row for row in rows}
            ordered = [by_title[title] for title in requested if title in by_title]
            return [self._memory_out(row) for row in ordered]
        return [self._memory_out(row) for row in self.repo.list_project_memories(project_id)]

    def write_memory_from_request(
        self, *, project_id: str, request: UpsertProjectMemoryRequest
    ) -> UpsertProjectMemoryResponse:
        return self.upsert_project_memory(
            project_id=project_id,
            title=request.title,
            content_markdown=request.contentMarkdown,
        )
