from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.envelope import err, ok
from app.schemas.settings import (
    SetAutoApproveRequest,
    SetModelRequest,
    SetApiKeyRequest,
    SetSystemPromptRequest,
    OpenRouterConfigResponse,
    SetApiKeyResponse,
    SetSystemPromptResponse,
    TestConnectionResponse,
    SyncModelsResponse,
)
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    try:
        data = SettingsService(db).get_settings()
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(status_code=500, content=err("Internal server error").model_dump())


@router.get("/auto-approve")
def get_auto_approve(db: Session = Depends(get_db)):
    try:
        data = SettingsService(db).get_auto_approve_rules()
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(status_code=500, content=err("Internal server error").model_dump())


@router.put("/auto-approve")
def set_auto_approve(request: SetAutoApproveRequest, db: Session = Depends(get_db)):
    try:
        data = SettingsService(db).set_auto_approve_rules(request.rules)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(status_code=500, content=err("Internal server error").model_dump())


@router.put("/system-prompt")
def set_system_prompt(request: SetSystemPromptRequest, db: Session = Depends(get_db)):
    """Set custom system prompt. Empty string resets to default."""
    try:
        data = SettingsService(db).set_system_prompt(request.systemPrompt)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(status_code=500, content=err("Internal server error").model_dump())


@router.put("/model")
def set_model(request: SetModelRequest, db: Session = Depends(get_db)):
    try:
        data = SettingsService(db).set_model(request.model)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(status_code=500, content=err("Internal server error").model_dump())


# OpenRouter configuration endpoints
@router.get("/openrouter")
def get_openrouter_config(db: Session = Depends(get_db)):
    """Get OpenRouter configuration including masked API key and connection status."""
    try:
        config = SettingsService(db).get_openrouter_config()
        response = OpenRouterConfigResponse(**config)
        return ok(response.model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(f"Failed to get config: {exc}").model_dump())


@router.put("/openrouter/api-key")
async def set_openrouter_api_key(request: SetApiKeyRequest, db: Session = Depends(get_db)):
    """Set OpenRouter API key and trigger model sync."""
    try:
        service = SettingsService(db)

        # Save API key
        result = service.set_openrouter_api_key(request.apiKey)

        # Trigger model sync
        try:
            models = await service.sync_openrouter_models()
            result["modelCount"] = len(models)
        except Exception as sync_error:
            # API key was saved, but sync failed
            result["error"] = f"API key saved but model sync failed: {sync_error}"

        response = SetApiKeyResponse(**result)
        return ok(response.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(f"Failed to set API key: {exc}").model_dump())


@router.post("/openrouter/test")
async def test_openrouter_connection(db: Session = Depends(get_db)):
    """Test connection to OpenRouter API using stored API key."""
    try:
        service = SettingsService(db)
        success, error = await service.test_openrouter_connection()
        response = TestConnectionResponse(success=success, error=error)
        return ok(response.model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(f"Test failed: {exc}").model_dump())


@router.post("/openrouter/sync")
async def sync_openrouter_models(db: Session = Depends(get_db)):
    """Manually trigger OpenRouter model sync."""
    try:
        service = SettingsService(db)
        models = await service.sync_openrouter_models()
        response = SyncModelsResponse(success=True, models=models, count=len(models))
        return ok(response.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(f"Sync failed: {exc}").model_dump())
