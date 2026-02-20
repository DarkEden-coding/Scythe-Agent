"""Async background task runner for Observer and Reflector."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.container import get_container
from app.services.memory.observational.service import (
    BufferedObservationChunk,
    ObservationError,
    ObservationMemoryService,
)
from app.services.token_counter import count_messages_tokens

logger = logging.getLogger(__name__)


class OMBackgroundRunner:
    """Manages async Observer/Reflector tasks per chat."""

    def __init__(self) -> None:
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._pending_requests: dict[str, dict] = {}

    def schedule_observation(
        self,
        *,
        chat_id: str,
        model: str,
        observer_model: str | None,
        reflector_model: str | None,
        observer_threshold: int,
        buffer_tokens: int,
        reflector_threshold: int,
        client,
        session_factory,
        event_bus,
    ) -> None:
        """Fire-and-forget: async buffering + threshold activation + reflection."""
        request = {
            "chat_id": chat_id,
            "model": model,
            "observer_model": observer_model,
            "reflector_model": reflector_model,
            "observer_threshold": observer_threshold,
            "buffer_tokens": buffer_tokens,
            "reflector_threshold": reflector_threshold,
            "client": client,
            "session_factory": session_factory,
            "event_bus": event_bus,
        }

        existing = self._running_tasks.get(chat_id)
        if existing and not existing.done():
            self._pending_requests[chat_id] = request
            return

        self._start_task(request)

    def cancel(self, chat_id: str) -> None:
        """Cancel running OM task (used on agent cancel/revert)."""
        self._pending_requests.pop(chat_id, None)
        task = self._running_tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

    def should_trigger_async_observation(
        self,
        *,
        unobserved_tokens: int,
        buffer_tokens: int,
        last_boundary: int,
    ) -> tuple[bool, int]:
        """Return (trigger, new_boundary) when a new async buffer interval is crossed."""
        interval = max(500, buffer_tokens)
        boundary = unobserved_tokens // interval
        return boundary > last_boundary, boundary

    def meets_observation_threshold(
        self,
        *,
        unobserved_tokens: int,
        message_tokens: int,
    ) -> bool:
        """Whether buffered observations should be activated into active context."""
        return unobserved_tokens >= message_tokens

    async def try_activate_buffered_observations(
        self,
        *,
        chat_id: str,
        svc: ObservationMemoryService,
        state: dict[str, Any],
        latest_observation,
        unobserved_messages: list[dict],
        trigger_token_count: int,
        model: str,
        observer_model: str | None,
        client,
    ):
        """Activate buffered chunks (or emergency-build one) into active observations."""
        buffer_state = state["buffer"]
        chunks: list[BufferedObservationChunk] = []
        for raw_chunk in buffer_state.get("chunks", []):
            if not isinstance(raw_chunk, dict):
                continue
            parsed = BufferedObservationChunk.from_dict(raw_chunk)
            if parsed is not None:
                chunks.append(parsed)

        # Fallback path: threshold reached before async boundary ever fired.
        if not chunks and unobserved_messages:
            fallback = await svc.run_observer_for_chunk(
                messages=unobserved_messages,
                model=model,
                observer_model=observer_model,
                client=client,
                trigger_token_count=trigger_token_count,
            )
            if fallback is not None:
                chunks.append(fallback)

        if not chunks:
            return latest_observation, state

        activated = svc.activate_buffered_observations(
            chat_id=chat_id,
            base_observation=latest_observation,
            chunks=chunks,
            trigger_token_count=trigger_token_count,
        )
        if activated is None:
            return latest_observation, state

        new_state = svc.update_state_from_observation(state=state, observation=activated)
        new_state["buffer"]["chunks"] = []
        new_state["buffer"]["lastBoundary"] = 0
        new_state["buffer"]["upToMessageId"] = activated.observed_up_to_message_id
        new_state["buffer"]["upToTimestamp"] = activated.timestamp
        svc.save_observational_state(chat_id, new_state)
        return activated, new_state

    def _get_prior_chunk_contents(
        self,
        state: dict,
        max_chunks: int = 2,
    ) -> list[str]:
        """Extract content strings from the last N buffered chunks for dedup context."""
        buffer = state.get("buffer") or {}
        raw_chunks = buffer.get("chunks") or []
        # Take the last max_chunks entries
        recent = raw_chunks[-max_chunks:] if len(raw_chunks) > max_chunks else raw_chunks
        contents: list[str] = []
        for raw in recent:
            if isinstance(raw, dict):
                text = raw.get("content", "")
                if isinstance(text, str) and text.strip():
                    contents.append(text.strip())
        return contents

    def _start_task(self, request: dict) -> None:
        chat_id = request["chat_id"]
        task = asyncio.create_task(
            self._run_observation_cycle(
                chat_id=request["chat_id"],
                model=request["model"],
                observer_model=request["observer_model"],
                reflector_model=request["reflector_model"],
                observer_threshold=request["observer_threshold"],
                buffer_tokens=request["buffer_tokens"],
                reflector_threshold=request["reflector_threshold"],
                client=request["client"],
                session_factory=request["session_factory"],
                event_bus=request["event_bus"],
            )
        )
        self._running_tasks[chat_id] = task

        def _cleanup(_t: asyncio.Task) -> None:
            self._running_tasks.pop(chat_id, None)
            pending = self._pending_requests.pop(chat_id, None)
            if pending is not None:
                self._start_task(pending)

        task.add_done_callback(_cleanup)

    async def _run_observation_cycle(
        self,
        *,
        chat_id: str,
        model: str,
        observer_model: str | None,
        reflector_model: str | None,
        observer_threshold: int,
        buffer_tokens: int,
        reflector_threshold: int,
        client,
        session_factory,
        event_bus,
    ) -> None:
        """Run passive buffering, threshold activation, then reflection if needed."""
        observing_emitted = False
        terminal_status_emitted = False
        try:
            with session_factory() as session:
                from app.db.repositories.chat_repo import ChatRepository

                repo = ChatRepository(session)
                svc = ObservationMemoryService(repo)

                db_messages = []
                for m in repo.list_messages(chat_id):
                    role = "assistant" if m.role == "assistant" else "user"
                    db_messages.append(
                        {
                            "role": role,
                            "content": m.content,
                            "_message_id": m.id,
                            "_timestamp": m.timestamp,
                        }
                    )

                latest_obs = repo.get_latest_observation(chat_id)
                state = svc.get_observational_state(
                    chat_id,
                    default_buffer_tokens=buffer_tokens,
                )
                state["buffer"]["tokens"] = max(500, buffer_tokens)

                # On first run, seed passive-buffer waterline from active observation.
                if latest_obs is not None:
                    if state["buffer"].get("upToMessageId") is None:
                        state["buffer"]["upToMessageId"] = latest_obs.observed_up_to_message_id
                    if state["buffer"].get("upToTimestamp") is None:
                        state["buffer"]["upToTimestamp"] = latest_obs.timestamp

                supplemental = self._build_supplemental_activity(
                    chat_id=chat_id,
                    repo=repo,
                    latest_observation_timestamp=(latest_obs.timestamp if latest_obs else None),
                )
                observation_messages = db_messages + supplemental

                _obs_active, unobserved_active = svc.get_unobserved_messages(
                    observation_messages,
                    latest_obs,
                )
                unobserved_tokens_active = count_messages_tokens(unobserved_active, model=model)

                _obs_buffer, unobserved_buffer = svc.split_messages_by_waterline(
                    observation_messages,
                    waterline_message_id=state["buffer"].get("upToMessageId"),
                    waterline_timestamp=state["buffer"].get("upToTimestamp"),
                )
                unobserved_tokens_buffer = count_messages_tokens(unobserved_buffer, model=model)

                should_buffer, boundary = self.should_trigger_async_observation(
                    unobserved_tokens=unobserved_tokens_buffer,
                    buffer_tokens=state["buffer"]["tokens"],
                    last_boundary=int(state["buffer"].get("lastBoundary") or 0),
                )

                if should_buffer and unobserved_buffer:
                    await event_bus.publish(
                        chat_id,
                        {
                            "type": "observation_status",
                            "payload": {"status": "observing", "chatId": chat_id},
                        },
                    )
                    observing_emitted = True

                    # Pass up to the last 2 buffered chunk contents for dedup
                    prior_chunk_contents = self._get_prior_chunk_contents(state, max_chunks=2)

                    try:
                        chunk = await svc.run_observer_for_chunk(
                            messages=unobserved_buffer,
                            model=model,
                            observer_model=observer_model,
                            client=client,
                            trigger_token_count=unobserved_tokens_buffer,
                            prior_chunks=prior_chunk_contents or None,
                        )
                    except ObservationError as exc:
                        await event_bus.publish(
                            chat_id,
                            {
                                "type": "error",
                                "payload": {
                                    "message": str(exc),
                                    "source": "observer",
                                    "retryable": True,
                                    "retryAction": "retry_observation",
                                },
                            },
                        )
                        return

                    if chunk is not None:
                        state["buffer"]["chunks"].append(chunk.to_dict())
                        if chunk.observed_up_to_message_id:
                            state["buffer"]["upToMessageId"] = chunk.observed_up_to_message_id
                        if chunk.observed_up_to_timestamp:
                            state["buffer"]["upToTimestamp"] = chunk.observed_up_to_timestamp
                        tokens_saved = max(0, unobserved_tokens_buffer - chunk.token_count)
                    else:
                        tokens_saved = 0

                    state["buffer"]["lastBoundary"] = boundary
                    svc.save_observational_state(chat_id, state)

                    await event_bus.publish(
                        chat_id,
                        {
                            "type": "observation_status",
                            "payload": {
                                "status": "observed",
                                "chatId": chat_id,
                                "tokensSaved": tokens_saved,
                            },
                        },
                    )
                    terminal_status_emitted = True

                if not self.meets_observation_threshold(
                    unobserved_tokens=unobserved_tokens_active,
                    message_tokens=observer_threshold,
                ):
                    if not terminal_status_emitted:
                        await event_bus.publish(
                            chat_id,
                            {
                                "type": "observation_status",
                                "payload": {
                                    "status": "observed",
                                    "chatId": chat_id,
                                    "tokensSaved": 0,
                                },
                            },
                        )
                        terminal_status_emitted = True
                    return

                if not observing_emitted:
                    await event_bus.publish(
                        chat_id,
                        {
                            "type": "observation_status",
                            "payload": {"status": "observing", "chatId": chat_id},
                        },
                    )
                    observing_emitted = True

                try:
                    latest_obs, state = await self.try_activate_buffered_observations(
                        chat_id=chat_id,
                        svc=svc,
                        state=state,
                        latest_observation=latest_obs,
                        unobserved_messages=unobserved_active,
                        trigger_token_count=unobserved_tokens_active,
                        model=model,
                        observer_model=observer_model,
                        client=client,
                    )
                except ObservationError as exc:
                    await event_bus.publish(
                        chat_id,
                        {
                            "type": "error",
                            "payload": {
                                "message": str(exc),
                                "source": "observer",
                                "retryable": True,
                                "retryAction": "retry_observation",
                            },
                        },
                    )
                    return

                if latest_obs is None:
                    await event_bus.publish(
                        chat_id,
                        {
                            "type": "observation_status",
                            "payload": {
                                "status": "observed",
                                "chatId": chat_id,
                                "tokensSaved": 0,
                            },
                        },
                    )
                    terminal_status_emitted = True
                    return

                tokens_saved = max(0, unobserved_tokens_active - latest_obs.token_count)
                await event_bus.publish(
                    chat_id,
                    {
                        "type": "observation_status",
                        "payload": {
                            "status": "observed",
                            "chatId": chat_id,
                            "tokensSaved": tokens_saved,
                        },
                    },
                )
                terminal_status_emitted = True

                if latest_obs.token_count >= reflector_threshold:
                    await event_bus.publish(
                        chat_id,
                        {
                            "type": "observation_status",
                            "payload": {"status": "reflecting", "chatId": chat_id},
                        },
                    )
                    terminal_status_emitted = False
                    tokens_before = latest_obs.token_count

                    try:
                        reflected = await svc.run_reflector(
                            chat_id=chat_id,
                            model=model,
                            reflector_model=reflector_model,
                            reflector_threshold=reflector_threshold,
                            client=client,
                        )
                    except ObservationError as exc:
                        await event_bus.publish(
                            chat_id,
                            {
                                "type": "error",
                                "payload": {
                                    "message": str(exc),
                                    "source": "reflector",
                                    "retryable": True,
                                    "retryAction": "retry_observation",
                                },
                            },
                        )
                        return

                    if reflected is not None:
                        latest_obs = reflected

                    state = svc.update_state_from_observation(
                        state=state,
                        observation=latest_obs,
                    )
                    state["buffer"]["upToMessageId"] = latest_obs.observed_up_to_message_id
                    state["buffer"]["upToTimestamp"] = latest_obs.timestamp
                    svc.save_observational_state(chat_id, state)

                    await event_bus.publish(
                        chat_id,
                        {
                            "type": "observation_status",
                            "payload": {
                                "status": "reflected",
                                "chatId": chat_id,
                                "tokensBefore": tokens_before,
                                "tokensAfter": latest_obs.token_count,
                            },
                        },
                    )
                    terminal_status_emitted = True

        except asyncio.CancelledError:
            if observing_emitted and not terminal_status_emitted:
                try:
                    await event_bus.publish(
                        chat_id,
                        {
                            "type": "observation_status",
                            "payload": {
                                "status": "observed",
                                "chatId": chat_id,
                                "tokensSaved": 0,
                            },
                        },
                    )
                except Exception:
                    logger.debug(
                        "OM cancel cleanup status publish failed for chat=%s",
                        chat_id,
                        exc_info=True,
                    )
            raise
        except Exception:
            logger.warning(
                "OM observation cycle failed for chat=%s", chat_id, exc_info=True
            )
            await event_bus.publish(
                chat_id,
                {
                    "type": "error",
                    "payload": {
                        "message": "Observation run failed unexpectedly.",
                        "source": "observer",
                        "retryable": True,
                        "retryAction": "retry_observation",
                    },
                },
            )

    def _build_supplemental_activity(
        self,
        *,
        chat_id: str,
        repo,
        latest_observation_timestamp: str | None,
    ) -> list[dict]:
        """Build synthetic rows from tool calls/reasoning created since last observation."""
        supplemental: list[dict] = []

        for tc in repo.list_tool_calls(chat_id):
            if (
                latest_observation_timestamp is not None
                and tc.timestamp <= latest_observation_timestamp
            ):
                continue

            parts = [
                f"Tool call: {tc.name}",
                f"Input: {tc.input_json}",
            ]
            if tc.output_text:
                parts.append(f"Output: {tc.output_text}")
            supplemental.append(
                {
                    "role": "tool",
                    "content": "\n".join(parts),
                    "_timestamp": tc.timestamp,
                }
            )

        for rb in repo.list_reasoning_blocks(chat_id):
            if (
                latest_observation_timestamp is not None
                and rb.timestamp <= latest_observation_timestamp
            ):
                continue
            supplemental.append(
                {
                    "role": "reasoning",
                    "content": rb.content,
                    "_timestamp": rb.timestamp,
                }
            )

        supplemental.sort(key=lambda row: str(row.get("_timestamp") or ""))
        return supplemental


def get_om_background_runner() -> OMBackgroundRunner:
    container = get_container()
    if container is None:
        raise RuntimeError("AppContainer is not initialized")
    return container.om_runner
