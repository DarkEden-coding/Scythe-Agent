"""Centralized OpenRouter API key resolution (DB first, env fallback)."""

from __future__ import annotations

import logging
import os

from app.db.repositories.settings_repo import SettingsRepository
from app.providers.openrouter.client import OpenRouterClient
from app.utils.encryption import decrypt, mask_api_key

logger = logging.getLogger(__name__)


class APIKeyResolver:
    """Resolves OpenRouter API key from DB or environment."""

    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._repo = settings_repo

    def resolve(self) -> str | None:
        """DB encrypted key first, then env var fallback, then None."""
        encrypted_key = self._repo.get_openrouter_api_key()
        if encrypted_key:
            try:
                return decrypt(encrypted_key)
            except Exception as e:
                logger.warning(f"Failed to decrypt API key: {e}")
        return os.getenv("OPENROUTER_API_KEY")

    def resolve_or_raise(self) -> str:
        """Like resolve() but raises ValueError if no key found."""
        key = self.resolve()
        if not key:
            raise ValueError("No OpenRouter API key configured")
        return key

    def resolve_masked(self) -> tuple[bool, str]:
        """Returns (has_key, masked_key_str) for UI display."""
        key = self.resolve()
        if not key:
            return False, ""
        return True, mask_api_key(key)

    def create_client(self) -> OpenRouterClient | None:
        """Resolve key + base_url, return configured client or None."""
        key = self.resolve()
        if not key:
            return None
        base_url = self._repo.get_openrouter_base_url()
        return OpenRouterClient(api_key=key, base_url=base_url)
