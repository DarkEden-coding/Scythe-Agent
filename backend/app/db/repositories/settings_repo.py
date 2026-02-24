from sqlalchemy import delete, select

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

    def set_active_model(
        self, model: str, updated_at: str, provider: str | None = None
    ) -> Settings:
        settings = self.get_settings()
        if settings is None:
            raise ValueError("Settings record missing")
        settings.active_model = model
        settings.active_model_provider = provider
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

    def set_brave_api_key(self, api_key: str, updated_at: str) -> Settings:
        """Set the Brave API key (should be encrypted before calling this)."""
        settings = self.get_settings()
        if settings is None:
            raise ValueError("Settings record missing")
        settings.brave_api_key = api_key
        settings.updated_at = updated_at
        return settings

    def get_brave_api_key(self) -> str | None:
        """Get the Brave API key (encrypted)."""
        settings = self.get_settings()
        if settings is None:
            return None
        return settings.brave_api_key

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

    def get_reasoning_level(self) -> str:
        """Get configured reasoning level, defaulting to medium."""
        settings = self.get_settings()
        if settings is None or not settings.reasoning_level:
            return "medium"
        return settings.reasoning_level

    def set_reasoning_level(self, reasoning_level: str, updated_at: str) -> Settings:
        """Set configured reasoning level."""
        settings = self.get_settings()
        if settings is None:
            raise ValueError("Settings record missing")
        settings.reasoning_level = reasoning_level
        settings.updated_at = updated_at
        return settings

    def get_memory_settings(self) -> dict:
        """Return memory-related settings as a dict with defaults applied."""
        s = self.get_settings()
        if s is None:
            return {
                "memory_mode": "observational",
                "observer_model": None,
                "reflector_model": None,
                "observer_threshold": 30000,
                "buffer_tokens": 6000,
                "reflector_threshold": 8000,
                "show_observations_in_chat": False,
                "tool_output_token_threshold": 2000,
                "tool_output_preview_tokens": 500,
            }
        observer_threshold = s.observer_threshold if s.observer_threshold is not None else 30000
        buffer_tokens = (
            s.buffer_tokens
            if s.buffer_tokens is not None
            else max(1000, observer_threshold // 5)
        )
        return {
            "memory_mode": s.memory_mode or "observational",
            "observer_model": s.observer_model,
            "reflector_model": s.reflector_model,
            "observer_threshold": observer_threshold,
            "buffer_tokens": buffer_tokens,
            "reflector_threshold": s.reflector_threshold if s.reflector_threshold is not None else 8000,
            "show_observations_in_chat": bool(s.show_observations_in_chat),
            "tool_output_token_threshold": s.tool_output_token_threshold if s.tool_output_token_threshold is not None else 2000,
            "tool_output_preview_tokens": s.tool_output_preview_tokens if s.tool_output_preview_tokens is not None else 500,
        }

    def get_sub_agent_settings(self) -> dict:
        """Return sub-agent settings as a dict with defaults."""
        s = self.get_settings()
        if s is None:
            return {
                "sub_agent_model": None,
                "sub_agent_model_provider": None,
                "sub_agent_model_key": None,
                "max_parallel_sub_agents": 4,
                "sub_agent_max_iterations": 25,
            }
        return {
            "sub_agent_model": s.sub_agent_model,
            "sub_agent_model_provider": s.sub_agent_model_provider,
            "sub_agent_model_key": s.sub_agent_model_key,
            "max_parallel_sub_agents": s.max_parallel_sub_agents if s.max_parallel_sub_agents is not None else 4,
            "sub_agent_max_iterations": s.sub_agent_max_iterations if s.sub_agent_max_iterations is not None else 25,
        }

    def set_sub_agent_model(
        self,
        model: str | None,
        provider: str | None = None,
        model_key: str | None = None,
        updated_at: str | None = None,
    ) -> None:
        """Set or clear sub-agent model override."""
        from app.utils.time import utc_now_iso

        s = self.get_settings()
        if s is None:
            raise ValueError("Settings record missing")
        s.sub_agent_model = model
        s.sub_agent_model_provider = provider
        s.sub_agent_model_key = model_key
        s.updated_at = updated_at or utc_now_iso()

    def set_sub_agent_settings(
        self,
        *,
        max_parallel_sub_agents: int | None = None,
        sub_agent_max_iterations: int | None = None,
        updated_at: str,
    ) -> None:
        """Update sub-agent numeric settings."""
        s = self.get_settings()
        if s is None:
            raise ValueError("Settings record missing")
        if max_parallel_sub_agents is not None:
            s.max_parallel_sub_agents = max(1, max_parallel_sub_agents)
        if sub_agent_max_iterations is not None:
            s.sub_agent_max_iterations = max(1, sub_agent_max_iterations)
        s.updated_at = updated_at

    def set_memory_settings(
        self,
        *,
        memory_mode: str | None = None,
        observer_model: str | None = None,
        reflector_model: str | None = None,
        observer_threshold: int | None = None,
        buffer_tokens: int | None = None,
        reflector_threshold: int | None = None,
        show_observations_in_chat: bool | None = None,
        tool_output_token_threshold: int | None = None,
        tool_output_preview_tokens: int | None = None,
        updated_at: str,
    ) -> None:
        s = self.get_settings()
        if s is None:
            raise ValueError("Settings record missing")
        if memory_mode is not None:
            s.memory_mode = memory_mode
        if observer_model is not None:
            s.observer_model = observer_model if observer_model.strip() else None
        if reflector_model is not None:
            s.reflector_model = reflector_model if reflector_model.strip() else None
        if observer_threshold is not None:
            s.observer_threshold = observer_threshold
        if buffer_tokens is not None:
            if buffer_tokens <= 0:
                raise ValueError("bufferTokens must be greater than 0")
            s.buffer_tokens = buffer_tokens
        if reflector_threshold is not None:
            s.reflector_threshold = reflector_threshold
        if show_observations_in_chat is not None:
            s.show_observations_in_chat = 1 if show_observations_in_chat else 0
        if tool_output_token_threshold is not None:
            s.tool_output_token_threshold = max(1, tool_output_token_threshold)
        if tool_output_preview_tokens is not None:
            s.tool_output_preview_tokens = max(1, tool_output_preview_tokens)
        s.updated_at = updated_at

    def list_auto_approve_rules(self) -> list[AutoApproveRule]:
        return list(self.db.scalars(select(AutoApproveRule).order_by(AutoApproveRule.created_at.asc())).all())

    def replace_auto_approve_rules(self, rules: list[AutoApproveRule]) -> list[AutoApproveRule]:
        self.db.execute(delete(AutoApproveRule))
        for rule in rules:
            self.db.add(rule)
        return rules
