from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    """Abstract interface for any LLM API provider."""

    async def create_chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int = 128,
        temperature: float = 0.0,
    ) -> str: ...


class ModelCatalogProvider(Protocol):
    """Abstract interface for model listing."""

    async def get_models(self) -> list[dict]: ...
