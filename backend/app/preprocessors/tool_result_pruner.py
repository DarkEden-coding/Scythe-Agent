from __future__ import annotations

from app.preprocessors.base import PreprocessorContext
from app.providers.base import LLMProvider

_MAX_TOOL_OUTPUT_CHARS = 4000


class ToolResultPrunerPreprocessor:
    """Truncate excessively long tool outputs in the message history."""

    name = "tool_result_pruner"
    priority = 40

    def __init__(self, max_chars: int = _MAX_TOOL_OUTPUT_CHARS):
        self._max_chars = max_chars

    async def process(
        self,
        ctx: PreprocessorContext,
        _provider: LLMProvider,
    ) -> PreprocessorContext:
        for msg in ctx.messages:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if not isinstance(content, str) or len(content) <= self._max_chars:
                    continue
                msg["content"] = content[: self._max_chars] + "\n... [truncated]"
        return ctx
