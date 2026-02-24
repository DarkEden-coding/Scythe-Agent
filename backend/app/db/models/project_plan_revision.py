from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.project_plan import ProjectPlan


class ProjectPlanRevision(Base):
    __tablename__ = "project_plan_revisions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("project_plans.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[str] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    checkpoint_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    last_editor: Mapped[str] = mapped_column(Text, nullable=False)
    approved_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    implementation_chat_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    plan: Mapped["ProjectPlan"] = relationship(back_populates="revisions")
