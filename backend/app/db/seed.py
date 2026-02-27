from __future__ import annotations

import json
import os
import logging

from sqlalchemy import select, inspect, text
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.base import Base
from app.db.models.mcp_server import MCPServer
from app.utils.time import utc_now_iso
from app.utils.encryption import encrypt
from app.db.models.auto_approve_rule import AutoApproveRule
from app.db.models.provider_model_cache import ProviderModelCache
from app.db.models.settings import Settings


logger = logging.getLogger(__name__)


def _ensure_settings_schema(db: Session) -> None:
    """Apply lightweight startup-safe schema guards for settings table."""
    bind = db.get_bind()
    inspector = inspect(bind)
    try:
        columns = {c["name"] for c in inspector.get_columns("settings")}
    except NoSuchTableError:
        # Fresh DB bootstraps (no Alembic run yet) need a minimal schema to start.
        # Importing models ensures all declarative mappings are registered.
        import app.db.models  # noqa: F401

        Base.metadata.create_all(bind=bind, checkfirst=True)
        columns = {c["name"] for c in inspect(bind).get_columns("settings")}
        logger.info("Created missing database tables during startup seed")
    if "active_model_provider" not in columns:
        db.execute(text("ALTER TABLE settings ADD COLUMN active_model_provider TEXT"))
        logger.info("Added missing settings.active_model_provider column during startup seed")
    if "reasoning_level" not in columns:
        db.execute(
            text("ALTER TABLE settings ADD COLUMN reasoning_level TEXT DEFAULT 'medium'")
        )
        logger.info("Added missing settings.reasoning_level column during startup seed")


def seed_app_data(db: Session) -> None:
    _ensure_settings_schema(db)
    settings = get_settings()
    now = utc_now_iso()

    if db.get(Settings, 1) is None:
        db.add(
            Settings(
                id=1,
                active_model=settings.default_active_model,
                active_model_provider="openrouter",
                context_limit=settings.default_context_limit,
                reasoning_level="medium",
                updated_at=now,
            )
        )

    # Auto-migrate OPENROUTER_API_KEY from environment variable to database
    settings_row = db.get(Settings, 1)
    if settings_row is not None:
        env_api_key = os.getenv("OPENROUTER_API_KEY")
        # If env var exists and DB doesn't have a key, migrate it
        if env_api_key and not settings_row.openrouter_api_key:
            try:
                encrypted_key = encrypt(env_api_key)
                settings_row.openrouter_api_key = encrypted_key
                logger.info(
                    "Migrated OpenRouter API key from environment variable to database"
                )
            except Exception as e:
                logger.error(f"Failed to migrate OpenRouter API key: {e}")

    existing_models = {m.id for m in db.scalars(select(ProviderModelCache)).all()}
    for idx, model in enumerate(settings.fallback_models):
        key = f"openrouter::{model}"
        if key not in existing_models:
            db.add(
                ProviderModelCache(
                    id=key,
                    provider="openrouter",
                    label=model,
                    context_limit=settings.default_context_limit,
                    raw_json=json.dumps({"id": model, "provider": "openrouter"}),
                    fetched_at=now,
                )
            )

    if db.get(AutoApproveRule, "aar-1") is None:
        db.add(
            AutoApproveRule(
                id="aar-1",
                field="tool",
                value="read_file",
                enabled=1,
                created_at=now,
            )
        )

    # Remove legacy mock MCP server if present (from old test seed)
    mock_server = db.get(MCPServer, "mcp-local-1")
    if mock_server is not None:
        db.delete(mock_server)
