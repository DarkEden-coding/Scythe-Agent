from __future__ import annotations

import logging

from app.preprocessors.base import Preprocessor, PreprocessorContext
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class PreprocessorPipeline:
    """Runs preprocessors in priority order with error isolation."""

    def __init__(self, preprocessors: list[Preprocessor] | None = None):
        self._preprocessors: list[Preprocessor] = sorted(
            preprocessors or [], key=lambda p: p.priority
        )

    def register(self, preprocessor: Preprocessor) -> None:
        self._preprocessors.append(preprocessor)
        self._preprocessors.sort(key=lambda p: p.priority)

    async def run(
        self,
        ctx: PreprocessorContext,
        provider: LLMProvider,
    ) -> PreprocessorContext:
        for pp in self._preprocessors:
            try:
                ctx = await pp.process(ctx, provider)
            except Exception:
                logger.warning(
                    "Preprocessor %s failed, skipping",
                    getattr(pp, "name", pp.__class__.__name__),
                    exc_info=True,
                )
        return ctx
