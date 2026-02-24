from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chat import Chat
    from app.db.models.sub_agent_run import SubAgentRun


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    checkpoint_id: Mapped[Optional[str]] = mapped_column(ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    input_json: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    parallel: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    parallel_group: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    chat: Mapped["Chat"] = relationship(back_populates="tool_calls")
    sub_agent_run: Mapped["SubAgentRun | None"] = relationship(
        back_populates="tool_call", uselist=False
    )
