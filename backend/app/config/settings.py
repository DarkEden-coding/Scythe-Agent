from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.defaults import (
    DEFAULT_ACTIVE_MODEL,
    DEFAULT_CONTEXT_LIMIT,
    FALLBACK_MODELS,
)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "dev"
    app_name: str = "scythe-backend"
    database_url: str = "sqlite:///./agentic.db"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    fallback_models: list[str] = FALLBACK_MODELS
    default_active_model: str = DEFAULT_ACTIVE_MODEL
    default_context_limit: int = DEFAULT_CONTEXT_LIMIT
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    oauth_redirect_base: str = "http://localhost:3001"
    oauth_redirect_uri: str = "http://localhost:1455/auth/callback"  # Codex OAuth app allows this; proxy on 1455 forwards to main app
    frontend_base: str = "http://localhost:5173"
    fs_allowed_roots: list[str] = []
    max_agent_iterations: int = 50


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
