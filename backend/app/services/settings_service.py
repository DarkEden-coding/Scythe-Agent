import logging

from sqlalchemy.orm import Session

from app.db.models.provider_model_cache import ProviderModelCache
from app.providers.reasoning import (
    extract_reasoning_capabilities,
    normalize_reasoning_setting,
)
from app.utils.encryption import encrypt
from app.utils.ids import generate_id
from app.utils.time import utc_now_iso

from app.db.models.auto_approve_rule import AutoApproveRule
from app.config.settings import get_settings
from app.db.repositories.settings_repo import SettingsRepository
from app.config.prompts import DEFAULT_SYSTEM_PROMPT
from app.schemas.settings import (
    AutoApproveRuleIn,
    AutoApproveRuleOut,
    GetAutoApproveResponse,
    GetSettingsResponse,
    ModelMetadata,
    SetModelResponse,
    SetAutoApproveResponse,
    SetReasoningLevelResponse,
    SetSystemPromptResponse,
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
        self.ensure_active_model_valid()
        settings_row = self.repo.get_settings()
        if settings_row is None:
            raise ValueError("Settings record missing")

        available_models = self._available_models()
        models_by_provider = self._models_by_provider()
        model_metadata = self._model_metadata()
        model_metadata_by_key = self._model_metadata_by_key()
        active_provider = settings_row.active_model_provider or self.repo.get_provider_for_model(
            settings_row.active_model
        )
        model_key = (
            self._to_model_key(active_provider, settings_row.active_model)
            if active_provider
            else None
        )

        rules = self.repo.list_auto_approve_rules()

        system_prompt = (
            settings_row.system_prompt
            if settings_row.system_prompt and settings_row.system_prompt.strip()
            else DEFAULT_SYSTEM_PROMPT
        )
        sub_settings = self.repo.get_sub_agent_settings()
        return GetSettingsResponse(
            model=settings_row.active_model,
            modelProvider=active_provider,
            modelKey=model_key,
            reasoningLevel=self.repo.get_reasoning_level(),
            availableModels=available_models,
            modelsByProvider=models_by_provider,
            modelMetadata=model_metadata,
            modelMetadataByKey=model_metadata_by_key,
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
            systemPrompt=system_prompt,
            subAgentModel=sub_settings.get("sub_agent_model"),
            subAgentModelProvider=sub_settings.get("sub_agent_model_provider"),
            subAgentModelKey=sub_settings.get("sub_agent_model_key"),
            maxParallelSubAgents=sub_settings.get("max_parallel_sub_agents") or 4,
            subAgentMaxIterations=sub_settings.get("sub_agent_max_iterations") or 25,
        )

    def _now(self) -> str:
        return utc_now_iso()

    @staticmethod
    def _to_model_key(provider: str, label: str) -> str:
        return f"{provider}::{label}"

    @staticmethod
    def _parse_model_key(model_key: str) -> tuple[str, str] | None:
        provider, sep, label = model_key.partition("::")
        if not sep or not provider.strip() or not label.strip():
            return None
        return provider.strip(), label.strip()

    def _available_models(self) -> list[str]:
        models = self.repo.list_models()
        labels = [m.label for m in models]
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
            if m.label in result:
                continue
            result[m.label] = self._extract_model_metadata(m, json)
        return result

    def _model_metadata_by_key(self) -> dict[str, ModelMetadata]:
        """Return metadata keyed by stable model key provider::label."""
        import json

        models = self.repo.list_models()
        result: dict[str, ModelMetadata] = {}
        for m in models:
            result[self._to_model_key(m.provider, m.label)] = self._extract_model_metadata(
                m, json
            )
        return result

    def _extract_model_metadata(self, model: ProviderModelCache, json_module) -> ModelMetadata:
        meta: dict = {}
        if model.context_limit is not None:
            meta["contextLimit"] = model.context_limit
        try:
            raw = json_module.loads(model.raw_json) if model.raw_json else {}
            pricing = raw.get("pricing") if isinstance(raw, dict) else {}
            if isinstance(pricing, dict):
                prompt = _parse_price(pricing.get("prompt"))
                completion = _parse_price(pricing.get("completion"))
                if prompt is not None or completion is not None:
                    avg_per_token = ((prompt or 0) + (completion or 0)) / 2
                    meta["pricePerMillion"] = round(avg_per_token * 1_000_000, 4)
            raw_model = raw if isinstance(raw, dict) else None
            reasoning_caps = extract_reasoning_capabilities(
                provider=model.provider,
                model_label=model.label,
                raw_model=raw_model,
            )
            meta["reasoningSupported"] = reasoning_caps.supported
            meta["reasoningLevels"] = list(reasoning_caps.levels)
            meta["defaultReasoningLevel"] = reasoning_caps.default_level
        except (json_module.JSONDecodeError, TypeError):
            pass
        return ModelMetadata(**meta)

    def _lookup_context_limit(self, model_label: str, provider: str | None = None) -> int:
        """Look up the context_limit for a model from ProviderModelCache."""
        models = self.repo.list_models()
        if provider:
            for m in models:
                if (
                    m.provider == provider
                    and m.label == model_label
                    and m.context_limit is not None
                ):
                    return m.context_limit
        for m in models:
            if m.label == model_label and m.context_limit is not None:
                return m.context_limit
        return self.app_settings.default_context_limit

    def ensure_active_model_valid(self) -> str:
        settings_row = self.repo.get_settings()
        if settings_row is None:
            raise ValueError("Settings record missing")

        models = self.repo.list_models()
        if not models:
            target_model = self.app_settings.default_active_model
            target_provider = settings_row.active_model_provider or "openrouter"
            if (
                settings_row.active_model != target_model
                or settings_row.active_model_provider != target_provider
                or settings_row.context_limit != self.app_settings.default_context_limit
            ):
                self.repo.set_active_model(
                    target_model, updated_at=self._now(), provider=target_provider
                )
                self.repo.set_context_limit(self.app_settings.default_context_limit)
                self.repo.commit()
            return target_model

        try:
            target = self._resolve_model_selection(
                model=settings_row.active_model,
                provider=settings_row.active_model_provider,
                model_key=None,
                models=models,
                settings_row=settings_row,
            )
        except ValueError:
            target = self._resolve_fallback_model(models)
        target_context_limit = target.context_limit or self.app_settings.default_context_limit
        if (
            settings_row.active_model != target.label
            or settings_row.active_model_provider != target.provider
            or settings_row.context_limit != target_context_limit
        ):
            self.repo.set_active_model(
                target.label, updated_at=self._now(), provider=target.provider
            )
            self.repo.set_context_limit(target_context_limit)
            self.repo.commit()
        return target.label

    def _resolve_fallback_model(self, models: list[ProviderModelCache]) -> ProviderModelCache:
        default_label = self.app_settings.default_active_model
        default_candidates = [row for row in models if row.label == default_label]
        if default_candidates:
            for preferred_provider in ("openrouter", "groq", "openai-sub"):
                for row in default_candidates:
                    if row.provider == preferred_provider:
                        return row
            return sorted(default_candidates, key=lambda row: (row.provider, row.id))[0]

        for preferred_provider in ("openrouter", "groq", "openai-sub"):
            provider_rows = [row for row in models if row.provider == preferred_provider]
            if provider_rows:
                return sorted(provider_rows, key=lambda row: row.label)[0]
        return sorted(models, key=lambda row: (row.provider, row.label, row.id))[0]

    def _resolve_model_selection(
        self,
        *,
        model: str,
        provider: str | None,
        model_key: str | None,
        models: list[ProviderModelCache],
        settings_row,
    ) -> ProviderModelCache:
        selected_provider = provider
        selected_model = model.strip()
        if model_key:
            parsed = self._parse_model_key(model_key.strip())
            if parsed is None:
                raise ValueError(f"Invalid model key: {model_key}")
            selected_provider, selected_model = parsed

        if selected_provider:
            for row in models:
                if row.provider == selected_provider and row.label == selected_model:
                    return row
            raise ValueError(
                f"Model is not available for provider {selected_provider}: {selected_model}"
            )

        candidates = [row for row in models if row.label == selected_model]
        if not candidates:
            raise ValueError(f"Model is not available: {selected_model}")
        if len(candidates) == 1:
            return candidates[0]

        active_provider = settings_row.active_model_provider
        if active_provider:
            for row in candidates:
                if row.provider == active_provider:
                    return row

        for preferred_provider in ("openrouter", "groq", "openai-sub"):
            for row in candidates:
                if row.provider == preferred_provider:
                    return row

        return sorted(candidates, key=lambda row: (row.provider, row.id))[0]

    def set_model(
        self, model: str, provider: str | None = None, model_key: str | None = None
    ) -> SetModelResponse:
        settings_row = self.repo.get_settings()
        if settings_row is None:
            raise ValueError("Settings record missing")

        models = self.repo.list_models()
        if not models:
            raise ValueError("No models are available")

        target = self._resolve_model_selection(
            model=model,
            provider=provider,
            model_key=model_key,
            models=models,
            settings_row=settings_row,
        )

        previous_model = settings_row.active_model
        # Look up the new model's context_limit and update the settings row
        new_context_limit = self._lookup_context_limit(target.label, provider=target.provider)
        self.repo.set_active_model(
            target.label, updated_at=self._now(), provider=target.provider
        )
        self.repo.set_context_limit(new_context_limit)
        self.repo.commit()
        return SetModelResponse(
            model=target.label, previousModel=previous_model, contextLimit=new_context_limit
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

    def get_groq_config(self) -> dict:
        """Get Groq configuration including masked API key and connection status."""
        from app.services.api_key_resolver import APIKeyResolver

        resolver = APIKeyResolver(self.repo)
        has_key, api_key_masked = resolver.resolve_masked("groq")
        models = self.repo.list_models()
        model_count = len([m for m in models if m.provider == "groq"])

        return {
            "apiKeyMasked": api_key_masked,
            "connected": has_key,
            "modelCount": model_count,
        }

    def set_groq_api_key(self, api_key: str) -> dict:
        """
        Validate, encrypt, and save Groq API key.
        Returns success status and model count.
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")

        api_key = api_key.strip()

        try:
            encrypted = encrypt(api_key)
        except Exception as e:
            logger.error(f"Failed to encrypt Groq API key: {e}")
            raise ValueError(f"Failed to encrypt API key: {e}") from e

        self.repo.set_groq_api_key(encrypted, updated_at=self._now())
        self.repo.commit()

        logger.info("Groq API key saved successfully")
        return {"success": True, "modelCount": 0}

    async def test_groq_connection(
        self, api_key: str | None = None
    ) -> tuple[bool, str | None]:
        """
        Test connection to Groq API.
        Uses provided API key or falls back to stored/env key.
        Returns (success, error_message).
        """
        from app.providers.groq.client import GroqClient
        from app.services.api_key_resolver import APIKeyResolver

        if api_key:
            client = GroqClient(api_key=api_key)
        else:
            resolver = APIKeyResolver(self.repo)
            client = resolver.create_client("groq")
            if not client:
                return False, "No API key configured"

        try:
            models = await client.get_models()
            if models:
                return True, None
            return False, "No models returned from API"
        except Exception as e:
            logger.error(f"Groq connection test failed: {e}")
            return False, str(e)

    def get_openai_sub_config(self) -> dict:
        """Get OpenAI Subscription config (OAuth status, model count)."""
        from app.services.api_key_resolver import APIKeyResolver

        resolver = APIKeyResolver(self.repo)
        has_token, masked = resolver.resolve_masked("openai-sub")
        models = self.repo.list_models()
        model_count = len([m for m in models if m.provider == "openai-sub"])

        return {
            "connected": has_token,
            "apiKeyMasked": masked if masked else "Signed in (OAuth)" if has_token else "",
            "modelCount": model_count,
        }

    def set_openai_sub_tokens(
        self, access_token: str | None, refresh_token: str | None
    ) -> dict:
        """Store OpenAI subscription OAuth tokens (encrypted)."""
        if not access_token:
            raise ValueError("Access token cannot be empty")
        try:
            encrypted_access = encrypt(access_token)
        except Exception as e:
            logger.error("Failed to encrypt OpenAI Sub access token: %s", e)
            raise ValueError("Failed to encrypt token") from e
        encrypted_refresh = None
        if refresh_token:
            try:
                encrypted_refresh = encrypt(refresh_token)
            except Exception as e:
                logger.warning("Failed to encrypt refresh token: %s", e)
        self.repo.set_openai_sub_tokens(
            encrypted_access, encrypted_refresh, updated_at=self._now()
        )
        self.repo.commit()
        return {"success": True}

    async def sync_openai_sub_models(self) -> list[str]:
        """Sync OpenAI Subscription models from API."""
        from app.providers.openai_sub.model_catalog import OpenAISubModelCatalogService
        from app.services.api_key_resolver import APIKeyResolver

        resolver = APIKeyResolver(self.repo)
        client = resolver.create_client("openai-sub")
        catalog = OpenAISubModelCatalogService(self.repo.db, client=client)
        return await catalog.sync_models_on_startup(force_refresh=True)

    async def test_openai_sub_connection(self) -> tuple[bool, str | None]:
        """Test connection using stored OAuth token."""
        from app.services.api_key_resolver import APIKeyResolver

        resolver = APIKeyResolver(self.repo)
        client = resolver.create_client("openai-sub")
        if not client:
            return False, "Not signed in"
        try:
            models = await client.get_models()
            if models:
                return True, None
            return False, "No models returned"
        except Exception as e:
            logger.error("OpenAI Sub connection test failed: %s", e)
            return False, str(e)

    async def sync_groq_models(self) -> list[str]:
        """
        Manually trigger Groq model sync.
        Returns list of model labels.
        """
        from app.providers.groq.model_catalog import GroqModelCatalogService
        from app.services.api_key_resolver import APIKeyResolver

        resolver = APIKeyResolver(self.repo)
        client = resolver.create_client("groq")
        if not client:
            raise ValueError("No Groq API key configured")

        catalog_service = GroqModelCatalogService(self.repo.db, client=client)
        labels = await catalog_service.sync_models_on_startup(force_refresh=True)
        return labels

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

    def get_brave_config(self) -> dict:
        """Get Brave configuration including masked API key and connection status."""
        from app.services.api_key_resolver import APIKeyResolver

        resolver = APIKeyResolver(self.repo)
        has_key, api_key_masked = resolver.resolve_masked("brave")
        return {
            "apiKeyMasked": api_key_masked,
            "connected": has_key,
        }

    def set_brave_api_key(self, api_key: str) -> dict:
        """Encrypt and save Brave API key."""
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")
        api_key = api_key.strip()
        try:
            encrypted = encrypt(api_key)
        except Exception as e:
            logger.error("Failed to encrypt Brave API key: %s", e)
            raise ValueError(f"Failed to encrypt API key: {e}") from e
        self.repo.set_brave_api_key(encrypted, updated_at=self._now())
        self.repo.commit()
        logger.info("Brave API key saved successfully")
        return {"success": True}

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

    def get_system_prompt(self) -> str:
        """Return effective system prompt (custom if set, else default)."""
        custom = self.repo.get_system_prompt()
        return custom if custom else DEFAULT_SYSTEM_PROMPT

    def set_system_prompt(self, prompt: str) -> SetSystemPromptResponse:
        """Set custom system prompt. Empty string resets to default."""
        self.repo.set_system_prompt(
            prompt if prompt.strip() else None,
            updated_at=self._now(),
        )
        self.repo.commit()
        effective = self.get_system_prompt()
        return SetSystemPromptResponse(systemPrompt=effective)

    def set_sub_agent_model(
        self, model: str | None, provider: str | None = None, model_key: str | None = None
    ) -> GetSettingsResponse:
        """Set or clear sub-agent model override. None clears (inherit main model)."""
        settings_row = self.repo.get_settings()
        if settings_row is None:
            raise ValueError("Settings record missing")
        if model is None or not model.strip():
            self.repo.set_sub_agent_model(None, None, None, updated_at=self._now())
            self.repo.commit()
            return self.get_settings()
        models = self.repo.list_models()
        if not models:
            raise ValueError("No models available")
        target = self._resolve_model_selection(
            model=model,
            provider=provider,
            model_key=model_key,
            models=models,
            settings_row=settings_row,
        )
        self.repo.set_sub_agent_model(
            target.label,
            provider=target.provider,
            model_key=self._to_model_key(target.provider, target.label),
            updated_at=self._now(),
        )
        self.repo.commit()
        return self.get_settings()

    def set_sub_agent_settings(
        self,
        *,
        max_parallel_sub_agents: int | None = None,
        sub_agent_max_iterations: int | None = None,
    ) -> None:
        """Update sub-agent numeric settings."""
        self.repo.set_sub_agent_settings(
            max_parallel_sub_agents=max_parallel_sub_agents,
            sub_agent_max_iterations=sub_agent_max_iterations,
            updated_at=self._now(),
        )
        self.repo.commit()

    def set_reasoning_level(self, reasoning_level: str) -> SetReasoningLevelResponse:
        """Set preferred reasoning effort level used for supported models."""
        normalized = normalize_reasoning_setting(reasoning_level)
        self.repo.set_reasoning_level(normalized, updated_at=self._now())
        self.repo.commit()
        return SetReasoningLevelResponse(reasoningLevel=normalized)

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
        labels = await catalog_service.sync_models_on_startup(force_refresh=True)
        return labels
