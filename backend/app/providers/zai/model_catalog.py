"""Z.ai model catalog service for syncing and caching available models."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models.provider_model_cache import ProviderModelCache
from app.db.repositories.settings_repo import SettingsRepository
from app.providers.zai.client import ZAiClient

MODEL_CACHE_TTL_SECONDS = 300
ZAI_MANUAL_MODELS = [
    "glm-4.7-flash",
]
ZAI_FALLBACK_MODELS = [
    "glm-4.5",
    "glm-4.7",
    "glm-4.7-flash",
    "glm-5",
]


class ZAiModelCatalogService:
    """Syncs and caches Z.ai models from the API."""

    def __init__(self, db: Session, client: ZAiClient | None = None) -> None:
        self.repo = SettingsRepository(db)
        self.client = client or ZAiClient()
        self.app_settings = get_settings()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_context_limit(item: dict) -> int | None:
        raw_value = item.get("context_length") or item.get("max_context_tokens") or item.get(
            "context_window"
        )
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
            normalized.append(
                ProviderModelCache(
                    id=f"zai::{model_id}",
                    provider="zai",
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
                id=f"zai::{model}",
                provider="zai",
                label=model,
                context_limit=self.app_settings.default_context_limit,
                raw_json=json.dumps({"id": model, "provider": "zai", "fallback": True}),
                fetched_at=fetched_at,
            )
            for model in ZAI_FALLBACK_MODELS
        ]

    def _manual_row(self, model: str, fetched_at: str, *, reason: str) -> ProviderModelCache:
        return ProviderModelCache(
            id=f"zai::{model}",
            provider="zai",
            label=model,
            context_limit=self.app_settings.default_context_limit,
            raw_json=json.dumps(
                {
                    "id": model,
                    "provider": "zai",
                    "manual": True,
                    "reason": reason,
                }
            ),
            fetched_at=fetched_at,
        )

    def _ensure_manual_rows(
        self,
        rows: list[ProviderModelCache],
        fetched_at: str,
        *,
        reason: str,
    ) -> list[ProviderModelCache]:
        merged = list(rows)
        labels = {row.label for row in merged}
        for model in ZAI_MANUAL_MODELS:
            if model in labels:
                continue
            merged.append(self._manual_row(model, fetched_at, reason=reason))
            labels.add(model)
        merged.sort(key=lambda m: m.label)
        return merged

    def _ensure_manual_rows_in_cache(self, fetched_at: str) -> None:
        existing_labels = {
            row.label for row in self.repo.list_models() if row.provider == "zai"
        }
        missing = [model for model in ZAI_MANUAL_MODELS if model not in existing_labels]
        if not missing:
            return
        for model in missing:
            self.repo.db.add(self._manual_row(model, fetched_at, reason="manual-cache"))
        self.repo.commit()

    def _available_model_labels(self) -> list[str]:
        cache_labels = [row.label for row in self.repo.list_models() if row.provider == "zai"]
        if cache_labels:
            return cache_labels
        return list(ZAI_FALLBACK_MODELS)

    def _cache_is_fresh(self) -> bool:
        """Return True if Z.ai cache exists and is within TTL."""
        models = [m for m in self.repo.list_models() if m.provider == "zai"]
        if not models:
            return False
        try:
            newest = max(m.fetched_at for m in models)
            fetched = datetime.fromisoformat(newest.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - fetched).total_seconds() < MODEL_CACHE_TTL_SECONDS
        except (ValueError, TypeError):
            return False

    async def sync_models_on_startup(self, *, force_refresh: bool = False) -> list[str]:
        """Sync models from Z.ai API when needed. Use cache when fresh unless force_refresh."""
        if not force_refresh and self._cache_is_fresh():
            self._ensure_manual_rows_in_cache(self._now())
            return self._available_model_labels()

        fetched_at = self._now()
        try:
            remote = await self.client.get_models()
            normalized = self._normalize(remote, fetched_at)
            if normalized:
                normalized = self._ensure_manual_rows(
                    normalized, fetched_at, reason="manual-augment"
                )
                self.repo.replace_models_for_provider("zai", normalized)
                self.repo.commit()
            elif any(m.provider == "zai" for m in self.repo.list_models()):
                self._ensure_manual_rows_in_cache(fetched_at)
            else:
                self.repo.replace_models_for_provider("zai", self._fallback_rows(fetched_at))
                self.repo.commit()
        except Exception:
            if any(m.provider == "zai" for m in self.repo.list_models()):
                self._ensure_manual_rows_in_cache(fetched_at)
            else:
                self.repo.replace_models_for_provider("zai", self._fallback_rows(fetched_at))
                self.repo.commit()

        return self._available_model_labels()
