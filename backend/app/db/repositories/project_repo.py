from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.chat import Chat
from app.db.models.message import Message
from app.db.models.project import Project


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_projects(self) -> list[Project]:
        stmt = select(Project).order_by(Project.sort_order.asc(), Project.last_active.desc())
        return list(self.db.scalars(stmt).all())

    def get_project(self, project_id: str) -> Project | None:
        return self.db.get(Project, project_id)

    def create_project(self, project: Project) -> Project:
        self.db.add(project)
        return project

    def update_project(self, project: Project, *, name: str | None = None, path: str | None = None) -> Project:
        if name is not None:
            project.name = name
        if path is not None:
            project.path = path
        return project

    def delete_project(self, project: Project) -> None:
        self.db.delete(project)

    def list_chats_for_project(self, project_id: str) -> list[Chat]:
        stmt = (
            select(Chat)
            .where(Chat.project_id == project_id)
            .order_by(Chat.is_pinned.desc(), Chat.sort_order.asc(), Chat.updated_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_chat(self, chat_id: str) -> Chat | None:
        return self.db.get(Chat, chat_id)

    def create_chat(self, chat: Chat) -> Chat:
        self.db.add(chat)
        return chat

    def update_chat(self, chat: Chat, *, title: str | None = None, is_pinned: bool | None = None) -> Chat:
        if title is not None:
            chat.title = title
        if is_pinned is not None:
            chat.is_pinned = 1 if is_pinned else 0
        return chat

    def delete_chat(self, chat: Chat) -> None:
        self.db.delete(chat)

    def get_last_message_for_chat(self, chat_id: str) -> Message | None:
        stmt = select(Message).where(Message.chat_id == chat_id).order_by(Message.timestamp.desc()).limit(1)
        return self.db.scalars(stmt).first()

    def get_message_count_for_chat(self, chat_id: str) -> int:
        stmt = select(func.count(Message.id)).where(Message.chat_id == chat_id)
        return int(self.db.scalar(stmt) or 0)

    def get_next_project_sort_order(self) -> int:
        stmt = select(func.max(Project.sort_order))
        current = self.db.scalar(stmt)
        return int(current) + 1 if current is not None else 0

    def get_next_chat_sort_order(self, project_id: str) -> int:
        stmt = select(func.max(Chat.sort_order)).where(Chat.project_id == project_id)
        current = self.db.scalar(stmt)
        return int(current) + 1 if current is not None else 0

    def set_project_order(self, project_ids: list[str]) -> None:
        for idx, project_id in enumerate(project_ids):
            project = self.get_project(project_id)
            if project is None:
                raise ValueError(f"Project not found: {project_id}")
            project.sort_order = idx

    def set_chat_order(self, project_id: str, chat_ids: list[str]) -> None:
        for idx, chat_id in enumerate(chat_ids):
            chat = self.get_chat(chat_id)
            if chat is None:
                raise ValueError(f"Chat not found: {chat_id}")
            if chat.project_id != project_id:
                raise ValueError(f"Chat {chat_id} does not belong to project {project_id}")
            chat.sort_order = idx

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
