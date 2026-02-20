from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ToolArtifact(Base):
    __tablename__ = "tool_artifacts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tool_call_id: Mapped[str] = mapped_column(ForeignKey("tool_calls.id", ondelete="CASCADE"), nullable=False)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    line_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preview_lines: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
