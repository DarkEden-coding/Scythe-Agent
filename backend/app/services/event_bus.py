from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


class EventBus:
    def __init__(self, *, max_sub_queue: int = 200):
        self._subs: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._sequence: dict[str, int] = defaultdict(int)
        self._max_sub_queue = max_sub_queue
        self._lock = asyncio.Lock()

    async def subscribe(self, chat_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._max_sub_queue)
        async with self._lock:
            self._subs[chat_id].add(queue)
        return queue

    async def unsubscribe(self, chat_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subs[chat_id].discard(queue)
            if not self._subs[chat_id]:
                self._subs.pop(chat_id, None)

    async def publish(self, chat_id: str, event: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            self._sequence[chat_id] += 1
            ordered_event = {
                **event,
                "chatId": chat_id,
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "sequence": self._sequence[chat_id],
            }

            dead: list[asyncio.Queue[dict[str, Any]]] = []
            for queue in self._subs.get(chat_id, set()):
                try:
                    queue.put_nowait(ordered_event)
                except asyncio.QueueFull:
                    dead.append(queue)
            for queue in dead:
                self._subs[chat_id].discard(queue)

            return ordered_event

    async def subscriber_count(self, chat_id: str) -> int:
        async with self._lock:
            return len(self._subs.get(chat_id, set()))


_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus

