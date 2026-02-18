from __future__ import annotations

import json
import os
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.utils.time import utc_now_iso
from app.utils.encryption import encrypt
from app.db.models.auto_approve_rule import AutoApproveRule
from app.db.models.provider_model_cache import ProviderModelCache
from app.db.models.settings import Settings


logger = logging.getLogger(__name__)


def seed_app_data(db: Session) -> None:
    settings = get_settings()
    now = utc_now_iso()

    if db.get(Settings, 1) is None:
        db.add(
            Settings(
                id=1,
                active_model=settings.default_active_model,
                context_limit=settings.default_context_limit,
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
