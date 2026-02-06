from __future__ import annotations

from app.providers.openrouter.client import OpenRouterClient


class RuntimeService:
    """Minimal deterministic runtime planner scaffold for Phase 6."""

    def __init__(self, client: OpenRouterClient | None = None):
        self.client = client or OpenRouterClient()

    async def plan_response(self, *, model: str, user_content: str) -> str:
        prompt = (
            "You are a planner that returns a short deterministic summary only. "
            "Do not request tool execution.\n"
            f"User message: {user_content[:500]}"
        )
        try:
            return await self.client.create_chat_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=96,
                temperature=0.0,
            )
        except Exception:
            return ""

