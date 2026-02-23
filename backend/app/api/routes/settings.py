from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.envelope import err, ok
from fastapi.responses import RedirectResponse
from app.middleware.error_handler import full_error_message

from app.config.settings import get_settings
from app.schemas.settings import (
    SetAutoApproveRequest,
    SetModelRequest,
    SetSubAgentModelRequest,
    SetSubAgentSettingsRequest,
    SetApiKeyRequest,
    SetSystemPromptRequest,
    SetReasoningLevelRequest,
    SetMemorySettingsRequest,
    OpenRouterConfigResponse,
    GroqConfigResponse,
    OpenAISubConfigResponse,
    SetApiKeyResponse,
    TestConnectionResponse,
    SyncModelsResponse,
    OpenAISubAuthStartResponse,
)
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings_route(db: Session = Depends(get_db)):
    try:
        data = SettingsService(db).get_settings()
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(full_error_message(exc)).model_dump()
        )


@router.get("/auto-approve")
def get_auto_approve(db: Session = Depends(get_db)):
    try:
        data = SettingsService(db).get_auto_approve_rules()
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(full_error_message(exc)).model_dump()
        )


@router.put("/auto-approve")
def set_auto_approve(request: SetAutoApproveRequest, db: Session = Depends(get_db)):
    try:
        data = SettingsService(db).set_auto_approve_rules(request.rules)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(full_error_message(exc)).model_dump()
        )


@router.put("/system-prompt")
def set_system_prompt(request: SetSystemPromptRequest, db: Session = Depends(get_db)):
    """Set custom system prompt. Empty string resets to default."""
    try:
        data = SettingsService(db).set_system_prompt(request.systemPrompt)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(full_error_message(exc)).model_dump()
        )


@router.put("/reasoning-level")
def set_reasoning_level(
    request: SetReasoningLevelRequest, db: Session = Depends(get_db)
):
    """Set preferred reasoning effort level for supported models."""
    try:
        data = SettingsService(db).set_reasoning_level(request.reasoningLevel)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(full_error_message(exc)).model_dump()
        )


@router.put("/sub-agent-model")
def set_sub_agent_model(
    request: SetSubAgentModelRequest, db: Session = Depends(get_db)
):
    """Set or clear sub-agent model override. Omit model or pass null to inherit main model."""
    try:
        data = SettingsService(db).set_sub_agent_model(
            model=request.model,
            provider=request.provider,
            model_key=request.modelKey,
        )
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(full_error_message(exc)).model_dump()
        )


@router.put("/sub-agent")
def set_sub_agent_settings(
    request: SetSubAgentSettingsRequest, db: Session = Depends(get_db)
):
    """Update sub-agent numeric settings (max parallel, iteration limit)."""
    try:
        SettingsService(db).set_sub_agent_settings(
            max_parallel_sub_agents=request.maxParallelSubAgents,
            sub_agent_max_iterations=request.subAgentMaxIterations,
        )
        data = SettingsService(db).get_settings()
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(full_error_message(exc)).model_dump()
        )


@router.put("/model")
def set_model(request: SetModelRequest, db: Session = Depends(get_db)):
    try:
        data = SettingsService(db).set_model(
            request.model, provider=request.provider, model_key=request.modelKey
        )
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(full_error_message(exc)).model_dump()
        )


# OpenRouter configuration endpoints
@router.get("/openrouter")
def get_openrouter_config(db: Session = Depends(get_db)):
    """Get OpenRouter configuration including masked API key and connection status."""
    try:
        config = SettingsService(db).get_openrouter_config()
        response = OpenRouterConfigResponse(**config)
        return ok(response.model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(f"Failed to get config: {exc}").model_dump()
        )


@router.put("/openrouter/api-key")
async def set_openrouter_api_key(
    request: SetApiKeyRequest, db: Session = Depends(get_db)
):
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
        return JSONResponse(
            status_code=500, content=err(f"Failed to set API key: {exc}").model_dump()
        )


@router.post("/openrouter/test")
async def test_openrouter_connection(db: Session = Depends(get_db)):
    """Test connection to OpenRouter API using stored API key."""
    try:
        service = SettingsService(db)
        success, error = await service.test_openrouter_connection()
        response = TestConnectionResponse(success=success, error=error)
        return ok(response.model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(f"Test failed: {exc}").model_dump()
        )


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
        return JSONResponse(
            status_code=500, content=err(f"Sync failed: {exc}").model_dump()
        )


# Groq configuration endpoints
@router.get("/groq")
def get_groq_config(db: Session = Depends(get_db)):
    """Get Groq configuration including masked API key and connection status."""
    try:
        config = SettingsService(db).get_groq_config()
        response = GroqConfigResponse(**config)
        return ok(response.model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(f"Failed to get config: {exc}").model_dump()
        )


@router.put("/groq/api-key")
async def set_groq_api_key(request: SetApiKeyRequest, db: Session = Depends(get_db)):
    """Set Groq API key and trigger model sync."""
    try:
        service = SettingsService(db)
        result = service.set_groq_api_key(request.apiKey)
        try:
            models = await service.sync_groq_models()
            result["modelCount"] = len(models)
        except Exception as sync_error:
            result["error"] = f"API key saved but model sync failed: {sync_error}"
        response = SetApiKeyResponse(**result)
        return ok(response.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(f"Failed to set API key: {exc}").model_dump()
        )


@router.post("/groq/test")
async def test_groq_connection(db: Session = Depends(get_db)):
    """Test connection to Groq API using stored API key."""
    try:
        service = SettingsService(db)
        success, error = await service.test_groq_connection()
        response = TestConnectionResponse(success=success, error=error)
        return ok(response.model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(f"Test failed: {exc}").model_dump()
        )


@router.post("/groq/sync")
async def sync_groq_models(db: Session = Depends(get_db)):
    """Manually trigger Groq model sync."""
    try:
        service = SettingsService(db)
        models = await service.sync_groq_models()
        response = SyncModelsResponse(success=True, models=models, count=len(models))
        return ok(response.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(f"Sync failed: {exc}").model_dump()
        )


# OpenAI Subscription (OAuth + Responses API) configuration endpoints
@router.get("/openai-sub")
def get_openai_sub_config(db: Session = Depends(get_db)):
    """Get OpenAI Subscription config (OAuth status, model count)."""
    try:
        config = SettingsService(db).get_openai_sub_config()
        response = OpenAISubConfigResponse(**config)
        return ok(response.model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(f"Failed to get config: {exc}").model_dump()
        )


@router.get("/openai-sub/auth/start")
def openai_sub_auth_start():
    """Start OAuth flow: return auth URL and state for PKCE."""
    import secrets

    from app.providers.openai_sub.oauth import build_auth_url

    settings = get_settings()
    redirect_uri = (
        settings.oauth_redirect_uri
        if settings.oauth_redirect_uri
        else f"{settings.oauth_redirect_base.rstrip('/')}/api/settings/openai-sub/callback"
    )
    state = secrets.token_urlsafe(32)
    auth_url = build_auth_url(redirect_uri, state)
    response = OpenAISubAuthStartResponse(authUrl=auth_url, state=state)
    return ok(response.model_dump())


@router.get("/openai-sub/callback")
async def openai_sub_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """OAuth callback: exchange code for tokens, store, redirect to frontend."""
    from app.providers.openai_sub.oauth import consume_verifier, exchange_code_for_token

    settings = get_settings()
    redirect_uri = (
        settings.oauth_redirect_uri
        if settings.oauth_redirect_uri
        else f"{settings.oauth_redirect_base.rstrip('/')}/api/settings/openai-sub/callback"
    )
    frontend_base = settings.frontend_base.rstrip("/")

    if error:
        return RedirectResponse(
            url=f"{frontend_base}/?openai-sub=error&message={error}",
            status_code=302,
        )
    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_base}/?openai-sub=error&message=missing_code_or_state",
            status_code=302,
        )

    verifier = consume_verifier(state)
    if not verifier:
        return RedirectResponse(
            url=f"{frontend_base}/?openai-sub=error&message=invalid_state",
            status_code=302,
        )

    try:
        token_data = await exchange_code_for_token(code, redirect_uri, verifier)
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        if not access_token:
            return RedirectResponse(
                url=f"{frontend_base}/?openai-sub=error&message=no_access_token",
                status_code=302,
            )
        service = SettingsService(db)
        service.set_openai_sub_tokens(access_token, refresh_token)
        await service.sync_openai_sub_models()
    except Exception as exc:
        return RedirectResponse(
            url=f"{frontend_base}/?openai-sub=error&message={str(exc)[:100]}",
            status_code=302,
        )

    return RedirectResponse(
        url=f"{frontend_base}/?openai-sub=success",
        status_code=302,
    )


@router.post("/openai-sub/test")
async def test_openai_sub_connection(db: Session = Depends(get_db)):
    """Test connection using stored OAuth token."""
    try:
        service = SettingsService(db)
        success, error = await service.test_openai_sub_connection()
        response = TestConnectionResponse(success=success, error=error)
        return ok(response.model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(f"Test failed: {exc}").model_dump()
        )


@router.post("/openai-sub/sync")
async def sync_openai_sub_models(db: Session = Depends(get_db)):
    """Manually trigger OpenAI Subscription model sync."""
    try:
        service = SettingsService(db)
        models = await service.sync_openai_sub_models()
        response = SyncModelsResponse(success=True, models=models, count=len(models))
        return ok(response.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(f"Sync failed: {exc}").model_dump()
        )


# Memory settings endpoints
@router.get("/memory")
def get_memory_settings(db: Session = Depends(get_db)):
    """Get memory mode and OM configuration."""
    try:
        from app.db.repositories.settings_repo import SettingsRepository
        repo = SettingsRepository(db)
        data = repo.get_memory_settings()
        return ok(data)
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(f"Failed to get memory settings: {exc}").model_dump()
        )


@router.post("/memory")
def set_memory_settings(request: SetMemorySettingsRequest, db: Session = Depends(get_db)):
    """Update memory mode and OM configuration."""
    try:
        from app.db.repositories.settings_repo import SettingsRepository
        from app.utils.time import utc_now_iso
        repo = SettingsRepository(db)
        repo.set_memory_settings(
            memory_mode=request.memoryMode,
            observer_model=request.observerModel,
            reflector_model=request.reflectorModel,
            observer_threshold=request.observerThreshold,
            buffer_tokens=request.bufferTokens,
            reflector_threshold=request.reflectorThreshold,
            show_observations_in_chat=request.showObservationsInChat,
            tool_output_token_threshold=request.toolOutputTokenThreshold,
            tool_output_preview_tokens=request.toolOutputPreviewTokens,
            updated_at=utc_now_iso(),
        )
        repo.commit()
        data = repo.get_memory_settings()
        return ok(data)
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(
            status_code=500, content=err(f"Failed to update memory settings: {exc}").model_dump()
        )
