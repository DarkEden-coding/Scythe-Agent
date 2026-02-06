from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.repositories.chat_repo import ChatRepository
from app.schemas.chat import ContextItemOut, SummarizeContextResponse
from app.services.event_bus import EventBus, get_event_bus


class SummarizeService:
    def __init__(self, db: Session, event_bus: EventBus | None = None):
        self.repo = ChatRepository(db)
        self.event_bus = event_bus or get_event_bus()

    async def summarize(self, chat_id: str) -> SummarizeContextResponse:
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        context = self.repo.list_context_items(chat_id)
        tokens_before = sum(c.tokens for c in context)

        for item in context:
            if item.type in {"conversation", "tool_output"}:
                self.repo.update_context_tokens(item, max(1, int(item.tokens * 0.3)))
        self.repo.commit()

        updated = self.repo.list_context_items(chat_id)
        tokens_after = sum(c.tokens for c in updated)
        out = [ContextItemOut(id=c.id, type=c.type, name=c.label, tokens=c.tokens) for c in updated]

        await self.event_bus.publish(chat_id, {"type": "context_update", "payload": {"contextItems": [i.model_dump() for i in out]}})
        return SummarizeContextResponse(contextItems=out, tokensBefore=tokens_before, tokensAfter=tokens_after)

