from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class MemoryBuildResult:
    messages: list[dict]
    metadata: dict = field(default_factory=dict)


class MemoryStrategy(Protocol):
    name: str

    async def build_context(
        self,
        *,
        chat_id: str,
        messages: list[dict],
        chat_repo,
    ) -> MemoryBuildResult: ...

    def maybe_update(
        self,
        *,
        chat_id: str,
        model: str,
        project_path: str | None,
        mem_cfg,
        client,
        session_factory,
        event_bus,
    ) -> None: ...
