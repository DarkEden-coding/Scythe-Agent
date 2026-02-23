"""Sub-agent run model: one row per spawn_sub_agent tool invocation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chat import Chat
    from app.db.models.tool_call import ToolCall


class SubAgentRun(Base):
    """Represents a single sub-agent execution spawned by spawn_sub_agent."""

    __tablename__ = "sub_agent_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    tool_call_id: Mapped[str] = mapped_column(ForeignKey("tool_calls.id", ondelete="CASCADE"), nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chat: Mapped["Chat"] = relationship(back_populates="sub_agent_runs")
    tool_call: Mapped["ToolCall"] = relationship(back_populates="sub_agent_run")
