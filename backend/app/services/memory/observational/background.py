"""Async background task runner for Observer and Reflector."""

from __future__ import annotations

import asyncio
import logging

from app.services.memory.observational.service import ObservationError, ObservationMemoryService
from app.services.token_counter import count_messages_tokens

logger = logging.getLogger(__name__)

# Module-level singleton: maps chat_id → running asyncio.Task
_running_tasks: dict[str, asyncio.Task] = {}


class OMBackgroundRunner:
    """Manages async Observer/Reflector tasks per chat."""

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
        """Fire-and-forget: run Observer then Reflector if needed."""
        # Cancel any existing task for this chat
        existing = _running_tasks.get(chat_id)
        if existing and not existing.done():
            existing.cancel()

        task = asyncio.create_task(
            self._run_observation_cycle(
                chat_id=chat_id,
                model=model,
                observer_model=observer_model,
                reflector_model=reflector_model,
                observer_threshold=observer_threshold,
                reflector_threshold=reflector_threshold,
                client=client,
                session_factory=session_factory,
                event_bus=event_bus,
            )
        )
        _running_tasks[chat_id] = task

        def _cleanup(t: asyncio.Task) -> None:
            _running_tasks.pop(chat_id, None)

        task.add_done_callback(_cleanup)

    def cancel(self, chat_id: str) -> None:
        """Cancel running OM task (used on agent cancel/revert)."""
        task = _running_tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

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
                    })

                # Check how many tokens are unobserved
                latest_obs = repo.get_latest_observation(chat_id)
                _observed, unobserved = svc.get_unobserved_messages(db_messages, latest_obs)
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
                        messages=db_messages,
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


# Module-level singleton instance
om_runner = OMBackgroundRunner()
