from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chat import Chat
    from app.db.models.project_plan import ProjectPlan


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    last_active: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    chats: Mapped[list["Chat"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    project_plans: Mapped[list["ProjectPlan"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
