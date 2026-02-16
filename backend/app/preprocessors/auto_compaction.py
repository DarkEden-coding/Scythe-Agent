from __future__ import annotations

import logging

from app.preprocessors.base import PreprocessorContext
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class AutoCompactionPreprocessor:
    """Compact conversation history when approaching context limit."""

    name = "auto_compaction"
    priority = 50  # Runs after token estimation

    def __init__(self, threshold_ratio: float = 0.85):
        self.threshold_ratio = threshold_ratio

    async def process(
        self,
        ctx: PreprocessorContext,
        provider: LLMProvider,
    ) -> PreprocessorContext:
        if ctx.estimated_tokens < ctx.context_limit * self.threshold_ratio:
            return ctx

        recent_count = 4
        if len(ctx.messages) <= recent_count:
            return ctx

        old_messages = ctx.messages[:-recent_count]
        recent_messages = ctx.messages[-recent_count:]

        try:
            summary = await provider.create_chat_completion(
                model=ctx.model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Summarize the following conversation history concisely. "
                            "Preserve key decisions, file paths mentioned, and tool results.\n\n"
                            + "\n".join(
                                f"[{m['role']}]: {str(m.get('content', ''))[:500]}"
                                for m in old_messages
                            )
                        ),
                    }
                ],
                max_tokens=512,
                temperature=0.0,
            )
        except Exception:
            logger.warning("Auto-compaction LLM call failed, skipping compaction", exc_info=True)
            return ctx

        compacted_message = {
            "role": "system",
            "content": f"[Conversation summary]: {summary}",
        }
        ctx.messages = [compacted_message] + recent_messages
        ctx.metadata["compaction_applied"] = True
        ctx.metadata["compacted_message_count"] = len(old_messages)
        return ctx
