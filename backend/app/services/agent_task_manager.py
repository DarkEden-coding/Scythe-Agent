from __future__ import annotations

import asyncio

from app.core.container import get_container


class AgentTaskManager:
    def __init__(self) -> None:
        self._running_tasks: dict[str, asyncio.Task] = {}

    def pop(self, chat_id: str) -> asyncio.Task | None:
        return self._running_tasks.pop(chat_id, None)

    def set(self, chat_id: str, task: asyncio.Task) -> None:
        self._running_tasks[chat_id] = task

    def get(self, chat_id: str) -> asyncio.Task | None:
        return self._running_tasks.get(chat_id)

    def delete_if_current(self, chat_id: str, task: asyncio.Task) -> None:
        if self._running_tasks.get(chat_id) is task:
            del self._running_tasks[chat_id]


def get_agent_task_manager() -> AgentTaskManager:
    container = get_container()
    if container is None:
        raise RuntimeError("AppContainer is not initialized")
    return container.agent_task_manager

