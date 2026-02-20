from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.project_repo import ProjectRepository
from app.schemas.chat import ContextItemOut, SummarizeContextResponse
from app.services.context_builder import build_context_items
from app.services.event_bus import EventBus, get_event_bus
from app.services.settings_service import SettingsService
from app.services.token_counter import TokenCounter


class SummarizeService:
    def __init__(self, db: Session, event_bus: EventBus | None = None):
        self.repo = ChatRepository(db)
        self.event_bus = event_bus or get_event_bus()

    async def summarize(self, chat_id: str) -> SummarizeContextResponse:
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        settings = SettingsService(self.repo.db).get_settings()
        token_counter = TokenCounter(model=settings.model)
        project_repo = ProjectRepository(self.repo.db)
        items = build_context_items(
            chat_id=chat_id,
            chat_repo=self.repo,
            project_repo=project_repo,
            token_counter=token_counter,
            context_limit=settings.contextLimit,
        )
        tokens_before = sum(i.tokens for i in items)

        summarized: list[tuple[str, str, str, int, str | None]] = []
        for i in items:
            tokens = i.tokens
            if i.type in {"conversation", "tool_output"}:
                tokens = max(1, int(tokens * 0.3))
            summarized.append((i.id, i.type, i.name, tokens, getattr(i, "full_name", None)))

        self.repo.replace_context_items(chat_id, [(x[0], x[1], x[2], x[3]) for x in summarized])
        self.repo.commit()

        tokens_after = sum(t for (_, _, _, t, _) in summarized)
        out = [
            ContextItemOut(id=id_, type=type_, name=name, tokens=t, full_name=fn)
            for id_, type_, name, t, fn in summarized
        ]
        await self.event_bus.publish(
            chat_id, {"type": "context_update", "payload": {"contextItems": [i.model_dump() for i in out]}}
        )
        return SummarizeContextResponse(
            contextItems=out, tokensBefore=tokens_before, tokensAfter=tokens_after
        )
