from __future__ import annotations

from app.preprocessors.base import PreprocessorContext
from app.providers.base import LLMProvider


class SystemPromptPreprocessor:
    """Inject system prompt at the start of the message list."""

    name = "system_prompt"
    priority = 10

    def __init__(self, default_prompt: str = "You are a helpful AI coding assistant."):
        self._default_prompt = default_prompt

    async def process(
        self,
        ctx: PreprocessorContext,
        provider: LLMProvider,
    ) -> PreprocessorContext:
        prompt = ctx.system_prompt or self._default_prompt
        if ctx.messages and ctx.messages[0].get("role") == "system":
            ctx.messages[0]["content"] = prompt
        else:
            ctx.messages.insert(0, {"role": "system", "content": prompt})
        return ctx
