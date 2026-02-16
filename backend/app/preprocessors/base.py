from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.providers.base import LLMProvider


@dataclass
class PreprocessorContext:
    """Mutable bag of state that flows through the preprocessor pipeline."""

    chat_id: str
    messages: list[dict]
    model: str
    context_limit: int
    estimated_tokens: int = 0
    system_prompt: str | None = None
    metadata: dict = field(default_factory=dict)


class Preprocessor(Protocol):
    """Single-responsibility message transform."""

    name: str
    priority: int  # Lower runs first (0-99)

    async def process(
        self,
        ctx: PreprocessorContext,
        provider: LLMProvider,
    ) -> PreprocessorContext: ...
