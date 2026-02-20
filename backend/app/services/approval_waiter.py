"""Waiter for blocking agent loop until user approves or rejects a pending tool call."""

from __future__ import annotations

import asyncio
import logging

from app.core.container import get_container

logger = logging.getLogger(__name__)


class ApprovalWaiter:
    def __init__(self) -> None:
        self._pending: dict[tuple[str, str], asyncio.Event] = {}
        self._result: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def register_and_wait(
        self, chat_id: str, tool_call_id: str, *, timeout: float = 300.0
    ) -> str:
        """Register a pending approval and wait for the user to approve or reject."""
        key = (chat_id, tool_call_id)
        ev = asyncio.Event()
        async with self._lock:
            self._pending[key] = ev
            self._result.pop(key, None)
        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
            return self._result.get(key, "timeout")
        except asyncio.TimeoutError:
            logger.warning(
                "Approval timeout for chat_id=%s tool_call_id=%s", chat_id, tool_call_id
            )
            return "timeout"
        finally:
            async with self._lock:
                self._pending.pop(key, None)
                self._result.pop(key, None)

    def signal_approved(self, chat_id: str, tool_call_id: str) -> None:
        key = (chat_id, tool_call_id)
        self._result[key] = "approved"
        ev = self._pending.get(key)
        if ev:
            ev.set()

    def signal_rejected(self, chat_id: str, tool_call_id: str) -> None:
        key = (chat_id, tool_call_id)
        self._result[key] = "rejected"
        ev = self._pending.get(key)
        if ev:
            ev.set()


def get_approval_waiter() -> ApprovalWaiter:
    container = get_container()
    if container is None:
        raise RuntimeError("AppContainer is not initialized")
    return container.approval_waiter

