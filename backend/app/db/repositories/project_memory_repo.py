from __future__ import annotations

from sqlalchemy import select

from app.db.models.project_memory import ProjectMemory
from app.db.repositories.base_repo import BaseRepository


class ProjectMemoryRepository(BaseRepository):
    def list_project_memories(self, project_id: str) -> list[ProjectMemory]:
        stmt = (
            select(ProjectMemory)
            .where(ProjectMemory.project_id == project_id)
            .order_by(ProjectMemory.title.asc(), ProjectMemory.updated_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_project_memory(self, memory_id: str) -> ProjectMemory | None:
        return self.db.get(ProjectMemory, memory_id)

    def get_project_memory_by_title(self, project_id: str, title: str) -> ProjectMemory | None:
        stmt = (
            select(ProjectMemory)
            .where(ProjectMemory.project_id == project_id, ProjectMemory.title == title)
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def get_project_memories_by_titles(self, project_id: str, titles: list[str]) -> list[ProjectMemory]:
        if not titles:
            return []
        stmt = (
            select(ProjectMemory)
            .where(ProjectMemory.project_id == project_id, ProjectMemory.title.in_(titles))
            .order_by(ProjectMemory.title.asc())
        )
        return list(self.db.scalars(stmt).all())

    def create_project_memory(self, memory: ProjectMemory) -> ProjectMemory:
        self.db.add(memory)
        return memory

    def delete_project_memory(self, memory: ProjectMemory) -> None:
        self.db.delete(memory)
