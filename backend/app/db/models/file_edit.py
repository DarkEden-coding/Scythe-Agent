from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Text  # type: ignore[import]
from sqlalchemy.orm import Mapped, mapped_column, relationship  # type: ignore[import]

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chat import Chat


class FileEdit(Base):
    __tablename__ = "file_edits"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    checkpoint_id: Mapped[Optional[str]] = mapped_column(ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True) = mapped_column(ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True) = mapped_column(ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True) = mapped_column(ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True) = mapped_column(ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True) = mapped_column(ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True) = mapped_column(ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True) = mapped_column(ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)

    chat: Mapped["Chat"] = relationship(back_populates="file_edits")
