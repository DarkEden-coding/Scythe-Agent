"""ObservationalMemoryPreprocessor — replaces observed messages with observation block."""

from __future__ import annotations

import logging

from app.preprocessors.base import PreprocessorContext
from app.providers.base import LLMProvider
from app.services.memory.observational.service import ObservationMemoryService
from app.utils.messages import strip_message_metadata

logger = logging.getLogger(__name__)


class ObservationalMemoryPreprocessor:
    """Replace observed messages with a compact observation block."""

    name = "observational_memory"
    priority = 50  # Same slot as AutoCompaction

    def __init__(self, chat_repo) -> None:
        self._chat_repo = chat_repo

    async def process(
        self,
        ctx: PreprocessorContext,
        provider: LLMProvider,
    ) -> PreprocessorContext:
        chat_id = ctx.chat_id

        # Refresh session so we see observations written by background tasks
        self._chat_repo.db.expire_all()

        # Load latest observation
        observation = self._chat_repo.get_latest_observation(chat_id)
        if observation is None:
            ctx.messages = strip_message_metadata(ctx.messages)
            return ctx

        svc = ObservationMemoryService(self._chat_repo)

        # Extract system prompt before splitting (SystemPromptPreprocessor prepends it)
        system_msg: dict | None = None
        messages_for_split = ctx.messages
        if ctx.messages and ctx.messages[0].get("role") == "system":
            system_msg = ctx.messages[0]
            messages_for_split = ctx.messages[1:]

        # Split remaining messages at waterline
        _observed, unobserved = svc.get_unobserved_messages(messages_for_split, observation)

        # Build context with observations replacing the observed messages
        new_messages = svc.build_context_with_observations(
            observation=observation,
            unobserved_messages=unobserved,
            system_prompt_msg=system_msg,
        )

        ctx.messages = new_messages
        ctx.metadata["observation_applied"] = True
        ctx.metadata["observation_generation"] = observation.generation
        ctx.metadata["observation_tokens"] = observation.token_count

        return ctx
