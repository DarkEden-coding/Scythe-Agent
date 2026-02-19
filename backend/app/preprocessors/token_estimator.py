from __future__ import annotations

import json

from app.preprocessors.base import PreprocessorContext
from app.providers.base import LLMProvider


class TokenEstimatorPreprocessor:
    """Estimate total token count of the message list."""

    name = "token_estimator"
    priority = 20

    async def process(
        self,
        ctx: PreprocessorContext,
        _provider: LLMProvider,
    ) -> PreprocessorContext:
        total = 0
        for msg in ctx.messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content) // 4
            elif isinstance(content, list):
                total += len(json.dumps(content)) // 4
        ctx.estimated_tokens = total
        return ctx
