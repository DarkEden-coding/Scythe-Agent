from __future__ import annotations

import httpx

from app.config.settings import get_settings


class OpenRouterClient:
    """OpenRouter API client for model catalog and chat completion calls."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.openrouter_base_url.rstrip("/")
        self._api_key = settings.openrouter_api_key

    async def get_models(self) -> list[dict]:
        if not self._api_key:
            return []
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self._base_url}/models", headers=headers)
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", [])
            return data if isinstance(data, list) else []

    async def create_chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int = 128,
        temperature: float = 0.0,
    ) -> str:
        if not self._api_key:
            return ""

        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(f"{self._base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()

        choices = body.get("choices", []) if isinstance(body, dict) else []
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message", {}) if isinstance(first, dict) else {}
        content = message.get("content", "") if isinstance(message, dict) else ""
        return str(content) if content is not None else ""
