"""Async background task runner for Observer and Reflector."""

from __future__ import annotations

import asyncio
import logging

from app.core.container import get_container
from app.services.memory.observational.service import ObservationError, ObservationMemoryService
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
        reflector_threshold: int,
        client,
        session_factory,
        event_bus,
    ) -> None:
        """Fire-and-forget: run Observer then Reflector if needed.

        Coalesces concurrent schedule requests per chat: when a run is already
        in progress, keep only the latest request and run it right after the
        current cycle completes.
        """
        request = {
            "chat_id": chat_id,
            "model": model,
            "observer_model": observer_model,
            "reflector_model": reflector_model,
            "observer_threshold": observer_threshold,
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

    def _start_task(self, request: dict) -> None:
        chat_id = request["chat_id"]
        task = asyncio.create_task(
            self._run_observation_cycle(
                chat_id=request["chat_id"],
                model=request["model"],
                observer_model=request["observer_model"],
                reflector_model=request["reflector_model"],
                observer_threshold=request["observer_threshold"],
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
        reflector_threshold: int,
        client,
        session_factory,
        event_bus,
    ) -> None:
        """Run Observer, then Reflector if needed, publishing SSE events."""
        observing_emitted = False
        terminal_status_emitted = False
        try:
            with session_factory() as session:
                from app.db.repositories.chat_repo import ChatRepository

                repo = ChatRepository(session)
                svc = ObservationMemoryService(repo)

                # Reload fresh messages from DB so we have proper _message_id waterlines
                db_messages = []
                for m in repo.list_messages(chat_id):
                    role = "assistant" if m.role == "assistant" else "user"
                    db_messages.append({
                        "role": role,
                        "content": m.content,
                        "_message_id": m.id,
                        "_timestamp": m.timestamp,
                    })

                latest_obs = repo.get_latest_observation(chat_id)
                supplemental = self._build_supplemental_activity(
                    chat_id=chat_id,
                    repo=repo,
                    latest_observation_timestamp=(latest_obs.timestamp if latest_obs else None),
                )
                observation_messages = db_messages + supplemental

                # Check how many tokens are unobserved. Supplemental activity rows
                # intentionally do not carry `_message_id`, so they remain unobserved
                # until a newer observation timestamp is written.
                _observed, unobserved = svc.get_unobserved_messages(
                    observation_messages, latest_obs
                )
                unobserved_tokens = count_messages_tokens(unobserved)

                if unobserved_tokens < observer_threshold:
                    # Not enough unobserved content — nothing to do
                    logger.debug(
                        "OM: chat=%s unobserved_tokens=%d < threshold=%d, skipping",
                        chat_id,
                        unobserved_tokens,
                        observer_threshold,
                    )
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

                await event_bus.publish(
                    chat_id,
                    {
                        "type": "observation_status",
                        "payload": {"status": "observing", "chatId": chat_id},
                    },
                )
                observing_emitted = True

                try:
                    new_obs = await svc.run_observer(
                        chat_id=chat_id,
                        messages=observation_messages,
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

            if new_obs is None:
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

            tokens_saved = unobserved_tokens - new_obs.token_count
            await event_bus.publish(
                chat_id,
                {
                    "type": "observation_status",
                    "payload": {
                        "status": "observed",
                        "chatId": chat_id,
                        "tokensSaved": max(0, tokens_saved),
                    },
                },
            )
            terminal_status_emitted = True

            # Check if we need to reflect
            if new_obs.token_count >= reflector_threshold:
                await event_bus.publish(
                    chat_id,
                    {
                        "type": "observation_status",
                        "payload": {"status": "reflecting", "chatId": chat_id},
                    },
                )
                terminal_status_emitted = False

                with session_factory() as session:
                    from app.db.repositories.chat_repo import ChatRepository

                    repo = ChatRepository(session)
                    svc = ObservationMemoryService(repo)
                    tokens_before = new_obs.token_count

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

                await event_bus.publish(
                    chat_id,
                    {
                        "type": "observation_status",
                        "payload": {
                            "status": "reflected",
                            "chatId": chat_id,
                            "tokensBefore": tokens_before,
                            "tokensAfter": (
                                reflected.token_count if reflected else tokens_before
                            ),
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
