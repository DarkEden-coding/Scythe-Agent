"""Observation data API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.envelope import err, ok
from app.db.repositories.chat_repo import ChatRepository

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
    except Exception:
        return JSONResponse(
            status_code=500, content=err("Internal server error").model_dump()
        )
