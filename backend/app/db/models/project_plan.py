from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chat import Chat
    from app.db.models.checkpoint import Checkpoint
    from app.db.models.project import Project
    from app.db.models.project_plan_revision import ProjectPlanRevision


class ProjectPlan(Base):
    __tablename__ = "project_plans"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    chat_id: Mapped[str] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    checkpoint_id: Mapped[str | None] = mapped_column(
        ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False, default="Implementation Plan")
    status: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    last_editor: Mapped[str] = mapped_column(Text, nullable=False, default="agent")
    approved_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    implementation_chat_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    chat: Mapped["Chat"] = relationship(back_populates="project_plans")
    project: Mapped["Project"] = relationship(back_populates="project_plans")
    checkpoint: Mapped["Checkpoint | None"] = relationship()
    revisions: Mapped[list["ProjectPlanRevision"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", passive_deletes=True
    )
