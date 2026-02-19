"""Core Observational Memory service: Observer and Reflector logic."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.db.models.observation import Observation
from app.services.memory.observational.prompts import (
    build_observer_prompt,
    build_reflector_prompt,
    parse_observation_output,
)
from app.utils.ids import generate_id
from app.utils.messages import strip_message_metadata
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)


def _count_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters."""
    return max(1, len(text) // 4) if text else 0


def _today_str() -> str:
    """Return today's date as a human-readable string like 'February 19, 2026'."""
    return datetime.now(timezone.utc).strftime("%B %d, %Y")


class ObservationMemoryService:
    """Runs Observer and Reflector to maintain observation log for a chat."""

    def __init__(self, chat_repo) -> None:
        self._chat_repo = chat_repo

    def get_unobserved_messages(
        self,
        all_messages: list[dict],
        observation: Observation | None,
    ) -> tuple[list[dict], list[dict]]:
        """
        Split messages into (observed, unobserved) based on waterline.

        Messages have `_message_id` attached by _assemble_messages().
        Messages without `_message_id` (e.g. new user message) are always unobserved.
        """
        if observation is None or observation.observed_up_to_message_id is None:
            return [], list(all_messages)

        waterline_id = observation.observed_up_to_message_id
        waterline_idx = None
        for i, msg in enumerate(all_messages):
            if msg.get("_message_id") == waterline_id:
                waterline_idx = i
                break

        if waterline_idx is None:
            # Waterline message not found — treat everything as unobserved
            return [], list(all_messages)

        observed = all_messages[: waterline_idx + 1]
        unobserved = all_messages[waterline_idx + 1 :]
        return observed, unobserved

    async def run_observer(
        self,
        *,
        chat_id: str,
        messages: list[dict],
        model: str,
        observer_model: str | None,
        client,
    ) -> Observation | None:
        """
        Run the Observer on unobserved messages.

        Returns a new Observation if successful, else None.
        """
        latest_obs = self._chat_repo.get_latest_observation(chat_id)
        _observed, unobserved = self.get_unobserved_messages(messages, latest_obs)

        if not unobserved:
            return None

        # Strip internal metadata before sending to Observer
        clean_unobserved = strip_message_metadata(unobserved)

        effective_model = observer_model or model
        today = _today_str()

        existing_content = latest_obs.content if latest_obs else None
        prompt_messages = build_observer_prompt(
            existing_observation=existing_content,
            new_messages=clean_unobserved,
            today=today,
        )

        try:
            raw_output = await client.create_chat_completion(
                model=effective_model,
                messages=prompt_messages,
                max_tokens=4096,
                temperature=0.1,
            )
        except Exception:
            logger.warning(
                "Observer LLM call failed for chat=%s", chat_id, exc_info=True
            )
            return None

        content, current_task, suggested_response = parse_observation_output(raw_output)
        if not content:
            return None

        # Find the last message ID in the unobserved list
        last_msg_id: str | None = None
        for msg in reversed(unobserved):
            mid = msg.get("_message_id")
            if mid:
                last_msg_id = mid
                break

        token_count = _count_tokens(content)
        generation = latest_obs.generation if latest_obs else 0

        if latest_obs and generation == latest_obs.generation:
            self._chat_repo.delete_observation(latest_obs)

        obs = self._chat_repo.create_observation(
            observation_id=generate_id("obs"),
            chat_id=chat_id,
            generation=generation,
            content=content,
            token_count=token_count,
            observed_up_to_message_id=last_msg_id,
            current_task=current_task,
            suggested_response=suggested_response,
            timestamp=utc_now_iso(),
        )
        self._chat_repo.commit()
        logger.info(
            "Observer created observation for chat=%s gen=%d tokens=%d",
            chat_id,
            generation,
            token_count,
        )
        return obs

    async def run_reflector(
        self,
        *,
        chat_id: str,
        model: str,
        reflector_model: str | None,
        reflector_threshold: int,
        client,
    ) -> Observation | None:
        """
        Run the Reflector if the current observation is too large.

        Returns a new higher-generation Observation if reflector ran, else None.
        """
        latest_obs = self._chat_repo.get_latest_observation(chat_id)
        if latest_obs is None:
            return None

        if latest_obs.token_count < reflector_threshold:
            return None

        effective_model = reflector_model or model
        prompt_messages = build_reflector_prompt(latest_obs.content)

        try:
            raw_output = await client.create_chat_completion(
                model=effective_model,
                messages=prompt_messages,
                max_tokens=4096,
                temperature=0.1,
            )
        except Exception:
            logger.warning(
                "Reflector LLM call failed for chat=%s", chat_id, exc_info=True
            )
            return None

        content, current_task, suggested_response = parse_observation_output(raw_output)
        if not content:
            return None

        new_generation = latest_obs.generation + 1
        token_count = _count_tokens(content)

        new_obs = self._chat_repo.create_observation(
            observation_id=generate_id("obs"),
            chat_id=chat_id,
            generation=new_generation,
            content=content,
            token_count=token_count,
            observed_up_to_message_id=latest_obs.observed_up_to_message_id,
            current_task=current_task,
            suggested_response=suggested_response,
            timestamp=utc_now_iso(),
        )
        # Delete superseded observations
        self._chat_repo.delete_observations_before_generation(chat_id, new_generation)
        self._chat_repo.commit()

        logger.info(
            "Reflector created observation for chat=%s gen=%d tokens=%d (was %d)",
            chat_id,
            new_generation,
            token_count,
            latest_obs.token_count,
        )
        return new_obs

    def build_context_with_observations(
        self,
        *,
        observation: Observation,
        unobserved_messages: list[dict],
        system_prompt_msg: dict | None,
    ) -> list[dict]:
        """
        Assemble context: [system] [observations block] [continuation hint] [recent msgs].

        The system_prompt_msg is the existing system message from the pipeline (already prepended).
        """
        result: list[dict] = []

        if system_prompt_msg:
            result.append(system_prompt_msg)

        obs_block = self.format_observations_for_context(
            observations=observation.content,
            current_task=observation.current_task,
        )
        result.append({"role": "system", "content": obs_block})

        if observation.suggested_response:
            result.append(
                {
                    "role": "user",
                    "content": (
                        "Here is a summary of the conversation history so far. "
                        "Use it naturally as your memory — don't acknowledge it explicitly."
                    ),
                }
            )
            result.append(
                {
                    "role": "assistant",
                    "content": (
                        "Understood. I'll continue from where we left off: "
                        + observation.suggested_response
                    ),
                }
            )

        # Append unobserved messages (stripped of internal metadata)
        clean_unobserved = strip_message_metadata(unobserved_messages)
        result.extend(clean_unobserved)

        return result

    def format_observations_for_context(
        self,
        observations: str,
        current_task: str | None,
    ) -> str:
        """Format observations as a system message for context injection."""
        lines = [
            "<observations>",
            "The following is a structured memory of this conversation so far.",
            "Treat it as your long-term memory. Prefer the MOST RECENT information for",
            "any conflicting facts. Assume planned actions in the past were completed",
            "unless explicitly stated otherwise. Do not mention this memory system — just",
            "use the information naturally.",
            "",
            observations,
        ]

        if current_task:
            lines.append("")
            lines.append(f"**Current task**: {current_task}")

        lines.append("</observations>")
        return "\n".join(lines)
