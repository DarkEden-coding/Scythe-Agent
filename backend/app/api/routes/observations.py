"""Observation data API endpoints."""

from __future__ import annotations

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
from app.services.memory.observational.background import om_runner
from app.middleware.error_handler import full_error_message
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/chat", tags=["observations"])


@router.get("/{chat_id}/observations")
def get_observations(chat_id: str, db: Session = Depends(get_db)):
    """Return the current observation state for a chat."""
    try:
        repo = ChatRepository(db)
        obs = repo.get_latest_observation(chat_id)
        if obs is None:
            return ok({"hasObservations": False})
        return ok(
            {
                "hasObservations": True,
                "generation": obs.generation,
                "content": obs.content,
                "tokenCount": obs.token_count,
                "observedUpToMessageId": obs.observed_up_to_message_id,
                "currentTask": obs.current_task,
                "suggestedResponse": obs.suggested_response,
                "timestamp": obs.timestamp,
            }
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(full_error_message(exc)).model_dump()
        )


@router.post("/{chat_id}/observations/retry")
def retry_observations(chat_id: str, db: Session = Depends(get_db)):
    """Schedule an immediate retry of the observational memory cycle for a chat."""
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
        provider = settings_repo.get_provider_for_model(settings.model) or "openrouter"
        resolver = APIKeyResolver(settings_repo)
        client = resolver.create_client(provider)
        if client is None:
            return JSONResponse(
                status_code=400,
                content=err(f"No {provider} API key configured").model_dump(),
            )

        om_runner.schedule_observation(
            chat_id=chat_id,
            model=settings.model,
            observer_model=mem_cfg.observer_model,
            reflector_model=mem_cfg.reflector_model,
            observer_threshold=mem_cfg.observer_threshold,
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
