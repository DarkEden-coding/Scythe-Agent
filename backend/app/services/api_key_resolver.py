"""Centralized API key resolution for LLM providers (DB first, env fallback)."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from app.db.repositories.settings_repo import SettingsRepository
from app.providers.groq.client import GroqClient
from app.providers.openai_sub.client import OpenAISubClient
from app.providers.openrouter.client import OpenRouterClient
from app.utils.encryption import decrypt, mask_api_key

if TYPE_CHECKING:
    from typing import Union

    LLMClient = Union[OpenRouterClient, GroqClient, OpenAISubClient]

logger = logging.getLogger(__name__)


class APIKeyResolver:
    """Resolves API keys for OpenRouter and Groq from DB or environment."""

    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._repo = settings_repo

    def resolve(self, provider: str = "openrouter") -> str | None:
        """DB encrypted key first, then env var fallback, then None."""
        if provider == "openrouter":
            encrypted_key = self._repo.get_openrouter_api_key()
            env_key = os.getenv("OPENROUTER_API_KEY")
        elif provider == "groq":
            encrypted_key = self._repo.get_groq_api_key()
            env_key = os.getenv("GROQ_API_KEY")
        elif provider == "openai-sub":
            encrypted_key = self._repo.get_openai_sub_access_token()
            env_key = os.getenv("OPENAI_SUB_ACCESS_TOKEN")
        elif provider == "brave":
            encrypted_key = self._repo.get_brave_api_key()
            env_key = os.getenv("BRAVE_API_KEY")
        else:
            return None
        if encrypted_key:
            try:
                return decrypt(encrypted_key)
            except Exception as e:
                logger.warning("Failed to decrypt %s API key: %s", provider, e)
        return env_key

    def resolve_or_raise(self, provider: str = "openrouter") -> str:
        """Like resolve() but raises ValueError if no key found."""
        key = self.resolve(provider)
        if not key:
            raise ValueError(f"No {provider} API key configured")
        return key

    def resolve_masked(self, provider: str = "openrouter") -> tuple[bool, str]:
        """Returns (has_key, masked_key_str) for UI display."""
        key = self.resolve(provider)
        if not key:
            return False, ""
        return True, mask_api_key(key)

    def create_client(self, provider: str = "openrouter") -> LLMClient | None:
        """Resolve key and return configured client for the given provider, or None."""
        if provider == "openrouter":
            key = self.resolve("openrouter")
            if not key:
                return None
            base_url = self._repo.get_openrouter_base_url()
            return OpenRouterClient(api_key=key, base_url=base_url)
        if provider == "groq":
            key = self.resolve("groq")
            if not key:
                return None
            return GroqClient(api_key=key)
        if provider == "openai-sub":
            token = self.resolve("openai-sub")
            if not token:
                return None
            return OpenAISubClient(access_token=token)
        return None
