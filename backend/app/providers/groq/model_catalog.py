"""Groq model catalog service for syncing and caching available models."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models.provider_model_cache import ProviderModelCache
from app.db.repositories.settings_repo import SettingsRepository
from app.providers.groq.client import GroqClient

MODEL_CACHE_TTL_SECONDS = 300
GROQ_FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama-3.1-70b-versatile",
]


class GroqModelCatalogService:
    """Syncs and caches Groq models from the API."""

    def __init__(self, db: Session, client: GroqClient | None = None) -> None:
        self.repo = SettingsRepository(db)
        self.client = client or GroqClient()
        self.app_settings = get_settings()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_context_limit(item: dict) -> int | None:
        raw_value = item.get("context_window", item.get("max_completion_tokens"))
        try:
            return int(raw_value) if raw_value is not None else None
        except (TypeError, ValueError):
            return None

    def _normalize(self, raw_models: list[dict], fetched_at: str) -> list[ProviderModelCache]:
        normalized: list[ProviderModelCache] = []
        seen_ids: set[str] = set()
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if not isinstance(model_id, str) or not model_id.strip():
                continue
            model_id = model_id.strip()
            if model_id in seen_ids:
                continue
            seen_ids.add(model_id)
            active = item.get("active", True)
            if not active:
                continue
            normalized.append(
                ProviderModelCache(
                    id=f"groq::{model_id}",
                    provider="groq",
                    label=model_id,
                    context_limit=self._parse_context_limit(item),
                    raw_json=json.dumps(item),
                    fetched_at=fetched_at,
                )
            )
        normalized.sort(key=lambda m: m.label)
        return normalized

    def _fallback_rows(self, fetched_at: str) -> list[ProviderModelCache]:
        return [
            ProviderModelCache(
                id=f"groq::{model}",
                provider="groq",
                label=model,
                context_limit=self.app_settings.default_context_limit,
                raw_json=json.dumps({"id": model, "provider": "groq", "fallback": True}),
                fetched_at=fetched_at,
            )
            for model in GROQ_FALLBACK_MODELS
        ]

    def _available_model_labels(self) -> list[str]:
        cache_labels = [row.label for row in self.repo.list_models() if row.provider == "groq"]
        if cache_labels:
            return cache_labels
        return list(GROQ_FALLBACK_MODELS)

    def _cache_is_fresh(self) -> bool:
        """Return True if groq cache exists and is within TTL."""
        models = [m for m in self.repo.list_models() if m.provider == "groq"]
        if not models:
            return False
        try:
            newest = max(m.fetched_at for m in models)
            fetched = datetime.fromisoformat(newest.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - fetched).total_seconds() < MODEL_CACHE_TTL_SECONDS
        except (ValueError, TypeError):
            return False

    async def sync_models_on_startup(self, *, force_refresh: bool = False) -> list[str]:
        """Sync models from Groq API when needed. Use cache when fresh unless force_refresh."""
        if not force_refresh and self._cache_is_fresh():
            return self._available_model_labels()

        fetched_at = self._now()
        try:
            remote = await self.client.get_models()
            normalized = self._normalize(remote, fetched_at)
            if normalized:
                self.repo.replace_models_for_provider("groq", normalized)
                self.repo.commit()
            elif not any(m.provider == "groq" for m in self.repo.list_models()):
                self.repo.replace_models_for_provider("groq", self._fallback_rows(fetched_at))
                self.repo.commit()
        except Exception:
            if not any(m.provider == "groq" for m in self.repo.list_models()):
                self.repo.replace_models_for_provider("groq", self._fallback_rows(fetched_at))
                self.repo.commit()

        return self._available_model_labels()
