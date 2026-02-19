from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.auto_approve_rule import AutoApproveRule
from app.db.models.provider_model_cache import ProviderModelCache
from app.db.models.settings import Settings
from app.db.repositories.base_repo import BaseRepository


class SettingsRepository(BaseRepository):
    def get_settings(self) -> Settings | None:
        return self.db.get(Settings, 1)

    def list_models(self) -> list[ProviderModelCache]:
        return list(self.db.scalars(select(ProviderModelCache).order_by(ProviderModelCache.label.asc())).all())

    def replace_models(self, models: list[ProviderModelCache]) -> list[ProviderModelCache]:
        self.db.execute(delete(ProviderModelCache).where(ProviderModelCache.provider == "openrouter"))
        for model in models:
            self.db.add(model)
        return models

    def replace_models_for_provider(
        self, provider: str, models: list[ProviderModelCache]
    ) -> list[ProviderModelCache]:
        """Replace all cached models for a given provider."""
        self.db.execute(delete(ProviderModelCache).where(ProviderModelCache.provider == provider))
        for model in models:
            self.db.add(model)
        return models

    def set_active_model(self, model: str, updated_at: str) -> Settings:
        settings = self.get_settings()
        if settings is None:
            raise ValueError("Settings record missing")
        settings.active_model = model
        settings.updated_at = updated_at
        return settings

    def set_context_limit(self, context_limit: int) -> Settings:
        settings = self.get_settings()
        if settings is None:
            raise ValueError("Settings record missing")
        settings.context_limit = context_limit
        return settings

    def set_openrouter_api_key(self, api_key: str, updated_at: str) -> Settings:
        """Set the OpenRouter API key (should be encrypted before calling this)."""
        settings = self.get_settings()
        if settings is None:
            raise ValueError("Settings record missing")
        settings.openrouter_api_key = api_key
        settings.updated_at = updated_at
        return settings

    def get_openrouter_api_key(self) -> str | None:
        """Get the OpenRouter API key (encrypted)."""
        settings = self.get_settings()
        if settings is None:
            return None
        return settings.openrouter_api_key

    def set_openrouter_base_url(self, base_url: str, updated_at: str) -> Settings:
        """Set the OpenRouter base URL."""
        settings = self.get_settings()
        if settings is None:
            raise ValueError("Settings record missing")
        settings.openrouter_base_url = base_url
        settings.updated_at = updated_at
        return settings

    def get_openrouter_base_url(self) -> str:
        """Get the OpenRouter base URL, with fallback to default."""
        settings = self.get_settings()
        if settings is None or not settings.openrouter_base_url:
            return "https://openrouter.ai/api/v1"
        return settings.openrouter_base_url

    def set_groq_api_key(self, api_key: str, updated_at: str) -> Settings:
        """Set the Groq API key (should be encrypted before calling this)."""
        settings = self.get_settings()
        if settings is None:
            raise ValueError("Settings record missing")
        settings.groq_api_key = api_key
        settings.updated_at = updated_at
        return settings

    def get_groq_api_key(self) -> str | None:
        """Get the Groq API key (encrypted)."""
        settings = self.get_settings()
        if settings is None:
            return None
        return settings.groq_api_key

    def set_openai_sub_tokens(
        self, access_token: str | None, refresh_token: str | None, updated_at: str
    ) -> Settings:
        """Set OpenAI subscription OAuth tokens (encrypted)."""
        settings = self.get_settings()
        if settings is None:
            raise ValueError("Settings record missing")
        settings.openai_sub_access_token = access_token
        settings.openai_sub_refresh_token = refresh_token
        settings.updated_at = updated_at
        return settings

    def get_openai_sub_access_token(self) -> str | None:
        """Get the OpenAI subscription access token (encrypted)."""
        settings = self.get_settings()
        if settings is None:
            return None
        return settings.openai_sub_access_token

    def get_openai_sub_refresh_token(self) -> str | None:
        """Get the OpenAI subscription refresh token (encrypted)."""
        settings = self.get_settings()
        if settings is None:
            return None
        return settings.openai_sub_refresh_token

    def get_provider_for_model(self, model_label: str) -> str | None:
        """Return the provider id for a model label, or None if not found."""
        models = self.list_models()
        for m in models:
            if m.label == model_label:
                return m.provider
        return None

    def get_system_prompt(self) -> str | None:
        """Get custom system prompt from settings, or None to use default."""
        settings = self.get_settings()
        if settings is None or not settings.system_prompt:
            return None
        return settings.system_prompt

    def set_system_prompt(self, prompt: str | None, updated_at: str) -> Settings:
        """Set custom system prompt. Pass None or empty to reset to default."""
        settings = self.get_settings()
        if settings is None:
            raise ValueError("Settings record missing")
        settings.system_prompt = prompt if prompt and prompt.strip() else None
        settings.updated_at = updated_at
        return settings

    def list_auto_approve_rules(self) -> list[AutoApproveRule]:
        return list(self.db.scalars(select(AutoApproveRule).order_by(AutoApproveRule.created_at.asc())).all())

    def replace_auto_approve_rules(self, rules: list[AutoApproveRule]) -> list[AutoApproveRule]:
        self.db.execute(delete(AutoApproveRule))
        for rule in rules:
            self.db.add(rule)
        return rules
