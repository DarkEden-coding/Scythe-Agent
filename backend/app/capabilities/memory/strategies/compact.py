from __future__ import annotations

from app.capabilities.memory.interfaces import MemoryBuildResult


class CompactMemoryStrategy:
    name = "compact"

    async def build_context(
        self,
        *,
        chat_id: str,
        messages: list[dict],
        chat_repo,
    ) -> MemoryBuildResult:
        return MemoryBuildResult(messages=list(messages), metadata={"memory_strategy": self.name})

    def maybe_update(
        self,
        *,
        chat_id: str,
        model: str,
        mem_cfg,
        client,
        session_factory,
        event_bus,
    ) -> None:
        return None
