from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.event_bus import get_event_bus

router = APIRouter(prefix="/api/chat", tags=["events"])


def _sse_frame(payload: dict) -> bytes:
    return f"data: {json.dumps(payload)}\n\n".encode("utf-8")


@router.get("/{chat_id}/events")
async def stream_events(chat_id: str, request: Request):
    event_bus = get_event_bus()
    queue = await event_bus.subscribe(chat_id)

    async def generator() -> AsyncGenerator[bytes, None]:
        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1)
                    yield _sse_frame(event)
                except TimeoutError:
                    heartbeat = {
                        "type": "heartbeat",
                        "chatId": chat_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": {},
                    }
                    yield _sse_frame(heartbeat)
        finally:
            await event_bus.unsubscribe(chat_id, queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
