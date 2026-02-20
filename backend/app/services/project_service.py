from pathlib import Path

from app.utils.ids import generate_id
from app.utils.time import utc_now_iso

from sqlalchemy.orm import Session

from app.capabilities.artifacts.store import ArtifactStore
from app.db.models.chat import Chat
from app.db.models.project import Project
from app.db.repositories.project_repo import ProjectRepository
from app.schemas.projects import (
    CreateChatResponse,
    CreateProjectResponse,
    DeleteChatResponse,
    DeleteProjectResponse,
    GetProjectsResponse,
    ProjectChatOut,
    ProjectOut,
    UpdateChatResponse,
    UpdateProjectResponse,
)


class ProjectService:
    def __init__(self, db: Session):
        self.repo = ProjectRepository(db)
        self._artifact_store = ArtifactStore()

    @staticmethod
    def _now() -> str:
        return utc_now_iso()

    @staticmethod
    def _new_id(prefix: str) -> str:
        return generate_id(prefix)

    def _normalize_dir_path(self, raw_path: str) -> str:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Directory does not exist: {raw_path}")
        return str(path)

    def _chat_out(self, chat: Chat) -> ProjectChatOut:
        last_msg = self.repo.get_last_message_for_chat(chat.id)
        return ProjectChatOut(
            id=chat.id,
            title=chat.title,
            lastMessage=last_msg.content if last_msg else "",
            timestamp=chat.updated_at,
            messageCount=self.repo.get_message_count_for_chat(chat.id),
            isPinned=bool(chat.is_pinned),
        )

    def _project_out(self, project: Project) -> ProjectOut:
        chats_out = [
            self._chat_out(chat)
            for chat in self.repo.list_chats_for_project(project.id)
        ]
        return ProjectOut(
            id=project.id,
            name=project.name,
            path=project.path,
            lastAccessed=project.last_active,
            sortOrder=project.sort_order,
            chats=chats_out,
        )

    def get_projects(self) -> GetProjectsResponse:
        projects = [self._project_out(project) for project in self.repo.list_projects()]
        return GetProjectsResponse(projects=projects)

    def create_project(self, *, name: str, path: str) -> CreateProjectResponse:
        now = self._now()
        normalized_path = self._normalize_dir_path(path)
        project = Project(
            id=self._new_id("proj"),
            name=name.strip(),
            path=normalized_path,
            last_active=now,
            sort_order=self.repo.get_next_project_sort_order(),
        )
        self.repo.create_project(project)
        self.repo.commit()
        return CreateProjectResponse(project=self._project_out(project))

    def update_project(
        self, *, project_id: str, name: str | None = None, path: str | None = None
    ) -> UpdateProjectResponse:
        project = self.repo.get_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")
        normalized_path = self._normalize_dir_path(path) if path is not None else None
        self.repo.update_project(
            project,
            name=name.strip() if name is not None else None,
            path=normalized_path,
        )
        project.last_active = self._now()
        self.repo.commit()
        return UpdateProjectResponse(project=self._project_out(project))

    def delete_project(self, *, project_id: str) -> DeleteProjectResponse:
        project = self.repo.get_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")
        from app.db.repositories.chat_repo import ChatRepository

        chat_repo = ChatRepository(self.repo.db)
        for chat in self.repo.list_chats_for_project(project_id):
            for artifact in chat_repo.list_tool_artifacts_for_chat(chat.id):
                self._artifact_store.delete_path(artifact.file_path)
        self.repo.delete_project(project)
        self.repo.commit()
        self._artifact_store.cleanup_project(project_id)
        return DeleteProjectResponse(deletedProjectId=project_id)

    def reorder_projects(self, project_ids: list[str]) -> GetProjectsResponse:
        self.repo.set_project_order(project_ids)
        self.repo.commit()
        return self.get_projects()

    def create_chat(
        self, *, project_id: str, title: str = "New chat"
    ) -> CreateChatResponse:
        project = self.repo.get_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")
        now = self._now()
        chat = Chat(
            id=self._new_id("chat"),
            project_id=project_id,
            title=title.strip() or "New chat",
            created_at=now,
            updated_at=now,
            sort_order=self.repo.get_next_chat_sort_order(project_id),
            is_pinned=0,
        )
        self.repo.create_chat(chat)
        project.last_active = now
        self.repo.commit()
        return CreateChatResponse(chat=self._chat_out(chat))

    def update_chat(
        self, *, chat_id: str, title: str | None = None, is_pinned: bool | None = None
    ) -> UpdateChatResponse:
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")
        self.repo.update_chat(
            chat,
            title=title.strip() if title is not None else None,
            is_pinned=is_pinned,
        )
        chat.updated_at = self._now()
        project = self.repo.get_project(chat.project_id)
        if project is not None:
            project.last_active = chat.updated_at
        self.repo.commit()
        return UpdateChatResponse(chat=self._chat_out(chat))

    def delete_chat(self, *, chat_id: str) -> DeleteChatResponse:
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")
        project_id = chat.project_id
        from app.db.repositories.chat_repo import ChatRepository

        chat_repo = ChatRepository(self.repo.db)
        for artifact in chat_repo.list_tool_artifacts_for_chat(chat_id):
            self._artifact_store.delete_path(artifact.file_path)
        self.repo.delete_chat(chat)
        self.repo.commit()

        remaining = self.repo.list_chats_for_project(project_id)
        fallback_chat_id = remaining[0].id if remaining else None
        return DeleteChatResponse(
            deletedChatId=chat_id, fallbackChatId=fallback_chat_id
        )

    def reorder_chats(
        self, *, project_id: str, chat_ids: list[str]
    ) -> GetProjectsResponse:
        project = self.repo.get_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")
        self.repo.set_chat_order(project_id, chat_ids)
        project.last_active = self._now()
        self.repo.commit()
        return self.get_projects()
