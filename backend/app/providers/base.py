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

    def count_tokens(self, text: str, model: str) -> int | None:
        """
        Count tokens in text for the given model.

        Returns:
            Token count, or None if this provider does not support token counting.
            Callers should fall back to tiktoken or another estimator when None.
        """
        return None  # Default: not supported


class ModelCatalogProvider(Protocol):
    """Abstract interface for model listing."""

    async def get_models(self) -> list[dict]: ...
