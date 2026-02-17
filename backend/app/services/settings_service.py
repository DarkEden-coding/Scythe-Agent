import logging

from sqlalchemy.orm import Session

from app.utils.encryption import encrypt
from app.utils.ids import generate_id
from app.utils.time import utc_now_iso

from app.db.models.auto_approve_rule import AutoApproveRule
from app.config.settings import get_settings
from app.db.repositories.settings_repo import SettingsRepository
from app.schemas.settings import (
    AutoApproveRuleIn,
    AutoApproveRuleOut,
    GetAutoApproveResponse,
    GetSettingsResponse,
    ModelMetadata,
    SetModelResponse,
    SetAutoApproveResponse,
)

logger = logging.getLogger(__name__)


def _parse_price(val: object) -> float | None:
    """Parse OpenRouter price string (per token) to float."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return None


class SettingsService:
    def __init__(self, db: Session):
        self.repo = SettingsRepository(db)
        self.app_settings = get_settings()

    def get_settings(self) -> GetSettingsResponse:
        settings_row = self.repo.get_settings()
        if settings_row is None:
            raise ValueError("Settings record missing")

        available_models = self._available_models()
        models_by_provider = self._models_by_provider()
        model_metadata = self._model_metadata()
        if settings_row.active_model not in set(available_models):
            self.ensure_active_model_valid()
            settings_row = self.repo.get_settings()
            if settings_row is None:
                raise ValueError("Settings record missing")

        rules = self.repo.list_auto_approve_rules()

        return GetSettingsResponse(
            model=settings_row.active_model,
            availableModels=available_models,
            modelsByProvider=models_by_provider,
            modelMetadata=model_metadata,
            contextLimit=settings_row.context_limit,
            autoApproveRules=[
                AutoApproveRuleOut(
                    id=r.id,
                    field=r.field,
                    value=r.value,
                    enabled=bool(r.enabled),
                    createdAt=r.created_at,
                )
                for r in rules
            ],
        )

    def _now(self) -> str:
        return utc_now_iso()

    def _available_models(self) -> list[str]:
        models = self.repo.list_models()
        labels = [m.label for m in models if m.provider == "openrouter"]
        return labels or list(self.app_settings.fallback_models)

    def _models_by_provider(self) -> dict[str, list[str]]:
        """Return models grouped by provider (e.g. {"openrouter": [...], "openai-direct": []})."""
        models = self.repo.list_models()
        result: dict[str, list[str]] = {}
        for m in models:
            if m.provider not in result:
                result[m.provider] = []
            result[m.provider].append(m.label)
        for prov in result:
            result[prov].sort()
        return result

    def _model_metadata(self) -> dict[str, ModelMetadata]:
        """Return metadata (contextLimit, pricePerMillion) per model label from raw_json."""
        import json

        models = self.repo.list_models()
        result: dict[str, ModelMetadata] = {}
        for m in models:
            meta: dict = {}
            if m.context_limit is not None:
                meta["contextLimit"] = m.context_limit
            try:
                raw = json.loads(m.raw_json) if m.raw_json else {}
                pricing = raw.get("pricing") if isinstance(raw, dict) else {}
                if isinstance(pricing, dict):
                    prompt = _parse_price(pricing.get("prompt"))
                    completion = _parse_price(pricing.get("completion"))
                    if prompt is not None or completion is not None:
                        avg_per_token = ((prompt or 0) + (completion or 0)) / 2
                        meta["pricePerMillion"] = round(avg_per_token * 1_000_000, 4)
            except (json.JSONDecodeError, TypeError):
                pass
            result[m.label] = ModelMetadata(**meta)
        return result

    def _lookup_context_limit(self, model_label: str) -> int:
        """Look up the context_limit for a model from ProviderModelCache."""
        models = self.repo.list_models()
        for m in models:
            if m.label == model_label and m.context_limit is not None:
                return m.context_limit
        return self.app_settings.default_context_limit

    def ensure_active_model_valid(self) -> str:
        settings_row = self.repo.get_settings()
        if settings_row is None:
            raise ValueError("Settings record missing")

        available = self._available_models()
        available_set = set(available)
        target = settings_row.active_model
        if target not in available_set:
            if self.app_settings.default_active_model in available_set:
                target = self.app_settings.default_active_model
            elif available:
                target = available[0]
            else:
                target = self.app_settings.default_active_model

        if target != settings_row.active_model:
            self.repo.set_active_model(target, updated_at=self._now())
            self.repo.commit()
        return target

    def set_model(self, model: str) -> SetModelResponse:
        settings_row = self.repo.get_settings()
        if settings_row is None:
            raise ValueError("Settings record missing")

        available = self._available_models()
        if model not in set(available):
            raise ValueError(f"Model is not available: {model}")

        previous_model = settings_row.active_model
        # Look up the new model's context_limit and update the settings row
        new_context_limit = self._lookup_context_limit(model)
        self.repo.set_active_model(model, updated_at=self._now())
        self.repo.set_context_limit(new_context_limit)
        self.repo.commit()
        return SetModelResponse(
            model=model, previousModel=previous_model, contextLimit=new_context_limit
        )

    def get_auto_approve_rules(self) -> GetAutoApproveResponse:
        rules = self.repo.list_auto_approve_rules()
        return GetAutoApproveResponse(
            rules=[
                AutoApproveRuleOut(
                    id=r.id,
                    field=r.field,
                    value=r.value,
                    enabled=bool(r.enabled),
                    createdAt=r.created_at,
                )
                for r in rules
            ]
        )

    def set_auto_approve_rules(
        self, rules: list[AutoApproveRuleIn]
    ) -> SetAutoApproveResponse:
        now = utc_now_iso()
        rows = [
            AutoApproveRule(
                id=generate_id("aar"),
                field=r.field,
                value=r.value,
                enabled=1 if r.enabled else 0,
                created_at=now,
            )
            for r in rules
        ]
        self.repo.replace_auto_approve_rules(rows)
        self.repo.commit()
        return SetAutoApproveResponse(
            rules=[
                AutoApproveRuleOut(
                    id=r.id,
                    field=r.field,
                    value=r.value,
                    enabled=bool(r.enabled),
                    createdAt=r.created_at,
                )
                for r in rows
            ]
        )

    def get_openrouter_config(self) -> dict:
        """Get OpenRouter configuration including masked API key and connection status."""
        from app.services.api_key_resolver import APIKeyResolver

        resolver = APIKeyResolver(self.repo)
        has_key, api_key_masked = resolver.resolve_masked()
        base_url = self.repo.get_openrouter_base_url()
        models = self.repo.list_models()
        model_count = len([m for m in models if m.provider == "openrouter"])

        return {
            "apiKeyMasked": api_key_masked,
            "baseUrl": base_url,
            "connected": has_key,
            "modelCount": model_count,
        }

    def set_openrouter_api_key(self, api_key: str) -> dict:
        """
        Validate, encrypt, and save OpenRouter API key.
        Returns success status and model count.
        """
        # Validate API key format
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")

        api_key = api_key.strip()

        # Basic validation - OpenRouter keys typically start with "sk-or-"
        if not api_key.startswith("sk-"):
            logger.warning(f"API key does not start with 'sk-': {api_key[:10]}")

        # Encrypt the API key
        try:
            encrypted = encrypt(api_key)
        except Exception as e:
            logger.error(f"Failed to encrypt API key: {e}")
            raise ValueError(f"Failed to encrypt API key: {e}")

        # Save to database
        self.repo.set_openrouter_api_key(encrypted, updated_at=self._now())
        self.repo.commit()

        logger.info("OpenRouter API key saved successfully")

        return {
            "success": True,
            "modelCount": 0,  # Will be updated after sync
        }

    async def test_openrouter_connection(
        self, api_key: str | None = None
    ) -> tuple[bool, str | None]:
        """
        Test connection to OpenRouter API.
        Uses provided API key or falls back to stored/env key.
        Returns (success, error_message).
        """
        from app.providers.openrouter.client import OpenRouterClient
        from app.services.api_key_resolver import APIKeyResolver

        if api_key:
            base_url = self.repo.get_openrouter_base_url()
            client = OpenRouterClient(api_key=api_key, base_url=base_url)
        else:
            resolver = APIKeyResolver(self.repo)
            client = resolver.create_client()
            if not client:
                return False, "No API key configured"

        try:
            models = await client.get_models()
            if models:
                return True, None
            return False, "No models returned from API"
        except Exception as e:
            logger.error(f"OpenRouter connection test failed: {e}")
            return False, str(e)

    async def sync_openrouter_models(self) -> list[str]:
        """
        Manually trigger OpenRouter model sync.
        Returns list of model labels.
        """
        from app.providers.openrouter.model_catalog import OpenRouterModelCatalogService
        from app.services.api_key_resolver import APIKeyResolver

        resolver = APIKeyResolver(self.repo)
        client = resolver.create_client()
        if not client:
            raise ValueError("No OpenRouter API key configured")

        catalog_service = OpenRouterModelCatalogService(self.repo.db, client=client)
        labels = await catalog_service.sync_models_on_startup()
        return labels
