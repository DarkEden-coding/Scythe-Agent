"""Waiter for blocking agent loop until user approves or rejects a pending tool call."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

_pending: dict[tuple[str, str], asyncio.Event] = {}
_result: dict[tuple[str, str], str] = {}
_lock = asyncio.Lock()


async def register_and_wait(
    chat_id: str, tool_call_id: str, *, timeout: float = 300.0
) -> str:
    """
    Register a pending approval and wait for the user to approve or reject.
    Returns "approved", "rejected", or "timeout".
    """
    key = (chat_id, tool_call_id)
    ev = asyncio.Event()
    async with _lock:
        _pending[key] = ev
        _result.pop(key, None)
    try:
        await asyncio.wait_for(ev.wait(), timeout=timeout)
        return _result.get(key, "timeout")
    except asyncio.TimeoutError:
        logger.warning(
            "Approval timeout for chat_id=%s tool_call_id=%s", chat_id, tool_call_id
        )
        return "timeout"
    finally:
        async with _lock:
            _pending.pop(key, None)
            _result.pop(key, None)


def signal_approved(chat_id: str, tool_call_id: str) -> None:
    """Signal that the user approved the tool call. Call from approve route."""
    key = (chat_id, tool_call_id)
    _result[key] = "approved"
    ev = _pending.get(key)
    if ev:
        ev.set()


def signal_rejected(chat_id: str, tool_call_id: str) -> None:
    """Signal that the user rejected the tool call. Call from reject route."""
    key = (chat_id, tool_call_id)
    _result[key] = "rejected"
    ev = _pending.get(key)
    if ev:
        ev.set()
