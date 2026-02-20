from __future__ import annotations

from app.capabilities.memory.interfaces import MemoryBuildResult
from app.services.memory.observational.background import get_om_background_runner
from app.services.memory.observational.service import ObservationMemoryService
from app.utils.messages import strip_message_metadata


class ObservationalMemoryStrategy:
    name = "observational"

    async def build_context(
        self,
        *,
        chat_id: str,
        messages: list[dict],
        chat_repo,
    ) -> MemoryBuildResult:
        chat_repo.db.expire_all()
        observation = chat_repo.get_latest_observation(chat_id)
        if observation is None:
            return MemoryBuildResult(
                messages=strip_message_metadata(messages),
                metadata={"memory_strategy": self.name},
            )

        svc = ObservationMemoryService(chat_repo)

        system_msg: dict | None = None
        messages_for_split = messages
        if messages and messages[0].get("role") == "system":
            system_msg = messages[0]
            messages_for_split = messages[1:]

        _observed, unobserved = svc.get_unobserved_messages(messages_for_split, observation)
        new_messages = svc.build_context_with_observations(
            observation=observation,
            unobserved_messages=unobserved,
            system_prompt_msg=system_msg,
        )

        return MemoryBuildResult(
            messages=new_messages,
            metadata={
                "memory_strategy": self.name,
                "observation_applied": True,
                "observation_generation": observation.generation,
                "observation_tokens": observation.token_count,
            },
        )

    def maybe_update(
        self,
        *,
        chat_id: str,
        model: str,
        mem_cfg,
        client,
        session_factory,
        event_bus,
    ) -> None:
        get_om_background_runner().schedule_observation(
            chat_id=chat_id,
            model=model,
            observer_model=mem_cfg.observer_model,
            reflector_model=mem_cfg.reflector_model,
            observer_threshold=mem_cfg.observer_threshold,
            buffer_tokens=mem_cfg.buffer_tokens,
            reflector_threshold=mem_cfg.reflector_threshold,
            client=client,
            session_factory=session_factory,
            event_bus=event_bus,
        )
