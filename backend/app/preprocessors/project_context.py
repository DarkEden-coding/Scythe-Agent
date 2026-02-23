"""ProjectContextPreprocessor — injects project directory overview into context."""

from __future__ import annotations

from app.initial_information import apply_initial_information
from app.preprocessors.base import PreprocessorContext
from app.providers.base import LLMProvider


class ProjectContextPreprocessor:
    """Inject a token-budgeted project directory overview as a system message.

    Runs at priority 15: after SystemPromptPreprocessor (10) so the system
    prompt is already present, and before TokenEstimatorPreprocessor (20).
    """

    name = "project_context"
    priority = 15

    def __init__(self, project_path: str | None) -> None:
        self._project_path = project_path

    async def process(
        self,
        ctx: PreprocessorContext,
        provider: LLMProvider,
    ) -> PreprocessorContext:
        if not self._project_path:
            return ctx
        ctx.messages = apply_initial_information(
            ctx.messages,
            project_path=self._project_path,
            model=ctx.model,
        )
        return ctx
