"""Async background task runner for Observer and Reflector."""

from __future__ import annotations

import asyncio
import logging

from app.services.memory.observational.service import ObservationMemoryService
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
        messages: list[dict],
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
                messages=messages,
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

    async def await_if_running(self, chat_id: str, timeout: float = 10.0) -> None:
        """Wait for in-flight OM task to complete before context assembly."""
        task = _running_tasks.get(chat_id)
        if task is None or task.done():
            return
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "OM background task for chat=%s timed out after %.1fs, proceeding without it",
                chat_id,
                timeout,
            )
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning(
                "OM background task for chat=%s raised an error", chat_id, exc_info=True
            )

    def cancel(self, chat_id: str) -> None:
        """Cancel running OM task (used on agent cancel/revert)."""
        task = _running_tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

    async def _run_observation_cycle(
        self,
        *,
        chat_id: str,
        messages: list[dict],
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
        try:
            await event_bus.publish(
                chat_id,
                {"type": "observation_status", "payload": {"status": "observing", "chatId": chat_id}},
            )

            with session_factory() as session:
                from app.db.repositories.chat_repo import ChatRepository

                repo = ChatRepository(session)
                svc = ObservationMemoryService(repo)

                # Check how many tokens are unobserved
                latest_obs = repo.get_latest_observation(chat_id)
                _observed, unobserved = svc.get_unobserved_messages(messages, latest_obs)
                unobserved_tokens = count_messages_tokens(unobserved)

                if unobserved_tokens < observer_threshold:
                    # Not enough unobserved content — nothing to do
                    return

                new_obs = await svc.run_observer(
                    chat_id=chat_id,
                    messages=messages,
                    model=model,
                    observer_model=observer_model,
                    client=client,
                )

            if new_obs is None:
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

            # Check if we need to reflect
            if new_obs.token_count >= reflector_threshold:
                await event_bus.publish(
                    chat_id,
                    {
                        "type": "observation_status",
                        "payload": {"status": "reflecting", "chatId": chat_id},
                    },
                )

                with session_factory() as session:
                    from app.db.repositories.chat_repo import ChatRepository

                    repo = ChatRepository(session)
                    svc = ObservationMemoryService(repo)
                    tokens_before = new_obs.token_count

                    reflected = await svc.run_reflector(
                        chat_id=chat_id,
                        model=model,
                        reflector_model=reflector_model,
                        reflector_threshold=reflector_threshold,
                        client=client,
                    )

                if reflected:
                    await event_bus.publish(
                        chat_id,
                        {
                            "type": "observation_status",
                            "payload": {
                                "status": "reflected",
                                "chatId": chat_id,
                                "tokensBefore": tokens_before,
                                "tokensAfter": reflected.token_count,
                            },
                        },
                    )

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "OM observation cycle failed for chat=%s", chat_id, exc_info=True
            )


# Module-level singleton instance
om_runner = OMBackgroundRunner()
