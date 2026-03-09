"""OpenAI Subscription model catalog backed by the local schema."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.provider_model_cache import ProviderModelCache
from app.db.repositories.settings_repo import SettingsRepository
from app.providers.openai_sub.models import OPENAI_SUB_MODELS

OPENAI_SUB_FALLBACK_MODELS = [
    (str(model["id"]), int(model["contextWindow"])) for model in OPENAI_SUB_MODELS
]


class OpenAISubModelCatalogService:
    """Caches OpenAI subscription models from the bundled schema."""

    def __init__(self, db: Session, client=None) -> None:
        self.repo = SettingsRepository(db)
        self.client = client

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _fallback_rows(self, fetched_at: str) -> list[ProviderModelCache]:
        return [
            ProviderModelCache(
                id=f"openai-sub::{model['id']}",
                provider="openai-sub",
                label=str(model["id"]),
                context_limit=int(model["contextWindow"]),
                raw_json=json.dumps({"provider": "openai-sub", **model}),
                fetched_at=fetched_at,
            )
            for model in OPENAI_SUB_MODELS
        ]

    async def sync_models_on_startup(self, *, force_refresh: bool = False) -> list[str]:
        """Refresh the cached catalog from the bundled schema."""
        del force_refresh
        rows = self._fallback_rows(self._now())
        self.repo.replace_models_for_provider("openai-sub", rows)
        self.repo.commit()
        return [r.label for r in rows]
