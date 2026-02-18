"""Token counting service: provider-native or tiktoken fallback."""

from __future__ import annotations

import logging
import re

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Model id patterns -> tiktoken encoding. Default cl100k_base for most models.
_ENCODING_MAP = [
    (re.compile(r"o1[-_]|o3|gpt-4o|gpt-4\.1", re.I), "o200k_base"),
    (re.compile(r"gpt-2|r50k|p50k", re.I), "r50k_base"),
]
_DEFAULT_ENCODING = "cl100k_base"


def _encoding_for_model(model: str) -> str:
    """Resolve tiktoken encoding name for a model id."""
    for pattern, encoding in _ENCODING_MAP:
        if pattern.search(model):
            return encoding
    return _DEFAULT_ENCODING


class TokenCounter:
    """Counts tokens using provider if available, otherwise tiktoken."""

    def __init__(
        self,
        model: str,
        provider: LLMProvider | None = None,
    ) -> None:
        self._model = model
        self._provider = provider
        self._tiktoken_enc = None

    def _get_tiktoken_encoding(self):
        """Lazy-load tiktoken encoding."""
        if self._tiktoken_enc is None:
            import tiktoken
            enc_name = _encoding_for_model(self._model)
            self._tiktoken_enc = tiktoken.get_encoding(enc_name)
        return self._tiktoken_enc

    def count(self, text: str) -> int:
        """
        Count tokens in text.

        Tries provider.count_tokens first; falls back to tiktoken when provider
        returns None or is not available.
        """
        if not text:
            return 0
        if self._provider is not None:
            try:
                n = self._provider.count_tokens(text, self._model)
                if n is not None:
                    return n
            except Exception as e:
                logger.debug("Provider count_tokens failed, using tiktoken: %s", e)
        enc = self._get_tiktoken_encoding()
        return len(enc.encode(text))
