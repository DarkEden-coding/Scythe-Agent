"""OpenAI Subscription model catalog - fetches models from API."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models.provider_model_cache import ProviderModelCache
from app.db.repositories.settings_repo import SettingsRepository

# Subscription models; /v1/models returns 403 for OAuth tokens
OPENAI_SUB_FALLBACK_MODELS = [
    ("gpt-5", 128_000),
    ("gpt-5-codex", 128_000),
    ("gpt-5-codex-mini", 128_000),
    ("gpt-5.1", 128_000),
    ("gpt-5.1-codex", 128_000),
    ("gpt-5.1-codex-max", 128_000),
    ("gpt-5.1-codex-mini", 128_000),
    ("gpt-5.2", 128_000),
    ("gpt-5.2-codex", 128_000),
    ("gpt-5.3-codex", 128_000),
]


class OpenAISubModelCatalogService:
    """Fetches and caches OpenAI subscription models from the API."""

    def __init__(self, db: Session, client=None) -> None:
        self.repo = SettingsRepository(db)
        self.client = client
        self.app_settings = get_settings()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_context_limit(item: dict) -> int | None:
        """Infer context limit from model metadata if available."""
        raw = item.get("context_length") or item.get("max_context_tokens")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    def _normalize(
        self, raw_models: list[dict], fetched_at: str
    ) -> list[ProviderModelCache]:
        normalized: list[ProviderModelCache] = []
        seen: set[str] = set()
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if not isinstance(model_id, str) or not model_id.strip():
                continue
            model_id = model_id.strip()
            if model_id in seen:
                continue
            seen.add(model_id)
            ctx = (
                self._parse_context_limit(item)
                or self.app_settings.default_context_limit
            )
            normalized.append(
                ProviderModelCache(
                    id=f"openai-sub::{model_id}",
                    provider="openai-sub",
                    label=model_id,
                    context_limit=ctx,
                    raw_json=json.dumps({"id": model_id, "provider": "openai-sub"}),
                    fetched_at=fetched_at,
                )
            )
        normalized.sort(key=lambda m: m.label)
        return normalized

    def _fallback_rows(self, fetched_at: str) -> list[ProviderModelCache]:
        return [
            ProviderModelCache(
                id=f"openai-sub::{label}",
                provider="openai-sub",
                label=label,
                context_limit=ctx,
                raw_json=json.dumps({"id": label, "provider": "openai-sub"}),
                fetched_at=fetched_at,
            )
            for label, ctx in OPENAI_SUB_FALLBACK_MODELS
        ]

    async def sync_models_on_startup(self, *, force_refresh: bool = False) -> list[str]:
        """Sync models from OpenAI API. Uses fallback if no client or API fails."""
        now = self._now()
        if self.client:
            try:
                raw = await self.client.get_models()
                normalized = self._normalize(raw, now)
                if normalized:
                    self.repo.replace_models_for_provider("openai-sub", normalized)
                    self.repo.commit()
                    return [r.label for r in normalized]
            except Exception:
                pass
        rows = self._fallback_rows(now)
        self.repo.replace_models_for_provider("openai-sub", rows)
        self.repo.commit()
        return [r.label for r in rows]
