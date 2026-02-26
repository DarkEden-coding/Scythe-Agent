from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Text  
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chat import Chat
    from app.db.models.message_attachment import MessageAttachment


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_id: Mapped[Optional[str]] = mapped_column(ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True)
    image_summarization: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_summarization_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    chat: Mapped["Chat"] = relationship(back_populates="messages")
    attachments: Mapped[list["MessageAttachment"]] = relationship(
        back_populates="message", cascade="all, delete-orphan", passive_deletes=True
    )
