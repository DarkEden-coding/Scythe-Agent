"""Brave Search LLM Context tool: fetch pre-extracted web content and summarize via sub-agent LLM."""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.types import ToolExecutionResult
from app.db.repositories.settings_repo import SettingsRepository
from app.services.api_key_resolver import APIKeyResolver
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

BRAVE_LLM_CONTEXT_URL = "https://api.search.brave.com/res/v1/llm/context"
GROUNDING_CHAR_BUDGET = 6000
SYSTEM_PROMPT = (
    "You are a concise summarizer. Given web search results and the user's query, "
    "produce a succinct report (2–5 paragraphs). Cite key facts and sources."
)


def _format_grounding(generic: list[dict]) -> str:
    """Format grounding.generic items into text for the LLM."""
    parts = []
    for item in generic:
        url = item.get("url") or ""
        title = item.get("title") or ""
        snippets = item.get("snippets") or []
        if not snippets:
            continue
        block = f"[{title}]({url})\n"
        for s in snippets:
            block += f"  {s}\n"
        parts.append(block)
    return "\n".join(parts)


def _truncate_grounding(text: str, max_chars: int = GROUNDING_CHAR_BUDGET) -> str:
    """Truncate grounding text to fit token budget."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[Truncated for length...]"


async def _handler(payload: dict, context: ToolExecutionContext) -> ToolExecutionResult:
    """Fetch Brave LLM Context, then summarize with sub-agent model."""
    q = (payload.get("q") or "").strip()
    if not q:
        return ToolExecutionResult(output="Error: q (search query) is required.", ok=False)
    if len(q) > 400:
        return ToolExecutionResult(
            output="Error: q must be 1–400 characters.", ok=False
        )

    chat_repo = context.chat_repo
    if not chat_repo:
        return ToolExecutionResult(output="Error: chat context required.", ok=False)

    settings_repo = SettingsRepository(chat_repo.db)
    api_key_resolver = APIKeyResolver(settings_repo)

    api_key = api_key_resolver.resolve("brave")
    if not api_key:
        return ToolExecutionResult(
            output="Brave Search API key not configured. Add it in Settings > Backend > API Keys.",
            ok=False,
        )

    maximum_number_of_tokens = payload.get("maximum_number_of_tokens") or 8192
    context_threshold_mode = payload.get("context_threshold_mode") or "balanced"

    params = {
        "q": q,
        "maximum_number_of_tokens": min(32768, max(1024, int(maximum_number_of_tokens))),
        "context_threshold_mode": context_threshold_mode,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                BRAVE_LLM_CONTEXT_URL,
                params=params,
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            )
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPStatusError as e:
        msg = e.response.text[:200] if e.response else str(e)
        logger.warning("Brave LLM Context API error: %s", msg)
        return ToolExecutionResult(
            output=f"Brave Search API error ({e.response.status_code}): {msg}",
            ok=False,
        )
    except Exception as e:
        logger.warning("Brave LLM Context request failed: %s", e)
        return ToolExecutionResult(
            output=f"Failed to fetch Brave Search: {e}",
            ok=False,
        )

    grounding = body.get("grounding") or {}
    generic = grounding.get("generic") or []
    if not generic:
        return ToolExecutionResult(output="No relevant content found.", ok=True)

    grounding_text = _format_grounding(generic)
    grounding_text = _truncate_grounding(grounding_text)

    settings_svc = SettingsService(chat_repo.db)
    sub_settings = settings_repo.get_sub_agent_settings()
    model = sub_settings.get("sub_agent_model")
    provider = sub_settings.get("sub_agent_model_provider")

    if not model:
        main_settings = settings_svc.get_settings()
        model = main_settings.model
        provider = main_settings.modelProvider or settings_repo.get_provider_for_model(model)

    if not provider:
        provider = "openrouter"

    llm_client = api_key_resolver.create_client(provider)
    if not llm_client:
        return ToolExecutionResult(
            output="No API key configured for summarization model. Configure OpenRouter or another provider.",
            ok=False,
        )

    user_content = f"Query: {q}\n\nWeb search results:\n{grounding_text}"

    try:
        summary = await llm_client.create_chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=1024,
            temperature=0.0,
        )
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning("LLM summarization failed: %s", e)
        return ToolExecutionResult(
            output=f"Summarization failed: {e}",
            ok=False,
        )

    return ToolExecutionResult(
        output=(summary or "").strip() or "No summary produced.",
        ok=True,
    )


TOOL_PLUGIN = ToolPlugin(
    name="brave_llm_context",
    description=(
        "Search the web for up-to-date information and produce a succinct report. "
        "Use for factual questions, current events, documentation lookup, or research. "
        "Returns a 2–5 paragraph summary citing sources. "
        "Requires Brave Search API key in Settings > Backend > API Keys."
    ),
    input_schema={
        "type": "object",
        "required": ["q"],
        "properties": {
            "q": {
                "type": "string",
                "description": "Search query (1–400 chars, max 50 words)",
                "minLength": 1,
                "maxLength": 400,
            },
            "maximum_number_of_tokens": {
                "type": "integer",
                "description": "Max tokens for Brave context (1024–32768)",
                "default": 8192,
            },
            "context_threshold_mode": {
                "type": "string",
                "enum": ["strict", "balanced", "lenient", "disabled"],
                "description": "Relevance threshold for content filtering",
                "default": "balanced",
            },
        },
    },
    approval_policy="rules",
    handler=_handler,
)
