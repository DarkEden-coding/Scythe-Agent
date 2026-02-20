"""Memory state API endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.envelope import err, ok
from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.db.session import get_sessionmaker
from app.services.api_key_resolver import APIKeyResolver
from app.services.event_bus import get_event_bus
from app.services.memory import MemoryConfig
from app.services.memory.observational.background import get_om_background_runner
from app.middleware.error_handler import full_error_message
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/chat", tags=["memory"])


@router.get("/{chat_id}/memory")
def get_memory_state(chat_id: str, db: Session = Depends(get_db)):
    """Return current memory state for a chat, independent of memory strategy."""
    try:
        repo = ChatRepository(db)
        observations = repo.list_observations(chat_id)
        observation_rows = [
            {
                "id": o.id,
                "generation": o.generation,
                "tokenCount": o.token_count,
                "observedUpToMessageId": o.observed_up_to_message_id,
                "currentTask": o.current_task,
                "suggestedResponse": o.suggested_response,
                "content": o.content,
                "timestamp": o.timestamp,
            }
            for o in observations
        ]
        state = repo.get_memory_state(chat_id)
        if state is not None:
            parsed_state: dict = {}
            try:
                raw = json.loads(state.state_json)
                if isinstance(raw, dict):
                    parsed_state = raw
            except Exception:
                parsed_state = {}

            if state.strategy == "observational":
                latest = repo.get_latest_observation(chat_id)
                if latest is not None:
                    parsed_state = {
                        **parsed_state,
                        "content": latest.content,
                        "currentTask": latest.current_task,
                        "suggestedResponse": latest.suggested_response,
                        "timestamp": latest.timestamp,
                    }

            return ok(
                {
                    "hasMemoryState": True,
                    "strategy": state.strategy,
                    "stateJson": state.state_json,
                    "state": parsed_state,
                    "observations": observation_rows,
                    "updatedAt": state.updated_at,
                }
            )

        return ok({"hasMemoryState": False, "observations": observation_rows})
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(full_error_message(exc)).model_dump()
        )


@router.post("/{chat_id}/memory/retry")
def retry_memory(chat_id: str, db: Session = Depends(get_db)):
    """Schedule an immediate retry of the active memory strategy for a chat."""
    try:
        chat_repo = ChatRepository(db)
        if chat_repo.get_chat(chat_id) is None:
            return JSONResponse(status_code=400, content=err("Chat not found").model_dump())

        settings_repo = SettingsRepository(db)
        mem_cfg = MemoryConfig.from_settings_repo(settings_repo)
        if mem_cfg.mode != "observational":
            return JSONResponse(
                status_code=400,
                content=err("Observational memory is disabled").model_dump(),
            )

        settings = SettingsService(db).get_settings()
        provider = (
            settings.modelProvider
            or settings_repo.get_provider_for_model(settings.model)
            or "openrouter"
        )
        resolver = APIKeyResolver(settings_repo)
        client = resolver.create_client(provider)
        if client is None:
            return JSONResponse(
                status_code=400,
                content=err(f"No {provider} API key configured").model_dump(),
            )

        get_om_background_runner().schedule_observation(
            chat_id=chat_id,
            model=settings.model,
            observer_model=mem_cfg.observer_model,
            reflector_model=mem_cfg.reflector_model,
            observer_threshold=mem_cfg.observer_threshold,
            buffer_tokens=mem_cfg.buffer_tokens,
            reflector_threshold=mem_cfg.reflector_threshold,
            client=client,
            session_factory=get_sessionmaker(),
            event_bus=get_event_bus(),
        )
        return ok({"scheduled": True})
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(full_error_message(exc)).model_dump()
        )
