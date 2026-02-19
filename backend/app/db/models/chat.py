from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.checkpoint import Checkpoint
    from app.db.models.todo import Todo
    from app.db.models.context_item import ContextItem
    from app.db.models.file_edit import FileEdit
    from app.db.models.file_snapshot import FileSnapshot
    from app.db.models.message import Message
    from app.db.models.observation import Observation
    from app.db.models.project import Project
    from app.db.models.reasoning_block import ReasoningBlock
    from app.db.models.tool_call import ToolCall


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_pinned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project: Mapped["Project"] = relationship(back_populates="chats")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", passive_deletes=True
    )
    checkpoints: Mapped[list["Checkpoint"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", passive_deletes=True
    )
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", passive_deletes=True
    )
    file_edits: Mapped[list["FileEdit"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", passive_deletes=True
    )
    reasoning_blocks: Mapped[list["ReasoningBlock"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", passive_deletes=True
    )
    context_items: Mapped[list["ContextItem"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", passive_deletes=True
    )
    file_snapshots: Mapped[list["FileSnapshot"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", passive_deletes=True
    )
    observations: Mapped[list["Observation"]] = relationship(
        "Observation", cascade="all, delete-orphan", passive_deletes=True,
        foreign_keys="Observation.chat_id",
    )
    todos: Mapped[list["Todo"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", passive_deletes=True
    )
