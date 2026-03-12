from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.core.container import get_container


@dataclass
class AgentTaskEntry:
    """Tracks the currently running task metadata for a chat."""

    task: asyncio.Task
    checkpoint_id: str | None = None


class AgentTaskManager:
    def __init__(self) -> None:
        self._running_tasks: dict[str, AgentTaskEntry] = {}

    def pop(self, chat_id: str) -> asyncio.Task | None:
        entry = self._running_tasks.pop(chat_id, None)
        return entry.task if entry is not None else None

    def set(
        self, chat_id: str, task: asyncio.Task, checkpoint_id: str | None = None
    ) -> None:
        """Store the active task and checkpoint for a chat."""

        self._running_tasks[chat_id] = AgentTaskEntry(
            task=task, checkpoint_id=checkpoint_id
        )

    def get(self, chat_id: str) -> asyncio.Task | None:
        entry = self._running_tasks.get(chat_id)
        return entry.task if entry is not None else None

    def get_checkpoint_id(self, chat_id: str) -> str | None:
        """Return the checkpoint ID for the active chat task, if known."""

        entry = self._running_tasks.get(chat_id)
        return entry.checkpoint_id if entry is not None else None

    def delete_if_current(self, chat_id: str, task: asyncio.Task) -> None:
        entry = self._running_tasks.get(chat_id)
        if entry is not None and entry.task is task:
            del self._running_tasks[chat_id]


def get_agent_task_manager() -> AgentTaskManager:
    container = get_container()
    if container is None:
        raise RuntimeError("AppContainer is not initialized")
    return container.agent_task_manager

