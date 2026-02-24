from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chat import Chat


class ReasoningBlock(Base):
    __tablename__ = "reasoning_blocks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    checkpoint_id: Mapped[Optional[str]] = mapped_column(ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    chat: Mapped["Chat"] = relationship(back_populates="reasoning_blocks")
