"""Vision capability detection for LLM models."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.repositories.settings_repo import SettingsRepository

# Fallback list of known vision-capable Groq models when API metadata lacks modality info
GROQ_VISION_MODELS: frozenset[str] = frozenset({
    "llama-3.2-90b-vision-preview",
    "llama-3.2-11b-vision-preview",
    "llama-3.2-90b-vision-instruct",
    "llama-3.2-11b-vision-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llava",
    "llava-13b",
})

# Fallback list for OpenAI Sub / Codex models with vision
OPENAI_SUB_VISION_MODELS: frozenset[str] = frozenset({
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4-vision-preview",
    "gpt-4o-2024",
    "gpt-4o-2024-05-13",
})


def model_has_vision(
    provider: str,
    model_label: str,
    settings_repo: SettingsRepository,
    raw_model: dict | None = None,
) -> bool:
    """Detect if the given model supports image/vision inputs.

    Uses provider API metadata (cached or passed via raw_model) when available.
    Falls back to known vision model lists when metadata lacks modality info.

    Args:
        provider: Provider id (e.g. openrouter, groq, openai-sub).
        model_label: Model label/id (e.g. anthropic/claude-3.5-sonnet).
        settings_repo: Repository for model cache lookup (used if raw_model not provided).
        raw_model: Optional pre-parsed model dict from API (avoids redundant lookup).

    Returns:
        True if the model supports vision inputs, False otherwise.
    """
    raw = raw_model
    if raw is None:
        models = settings_repo.list_models()
        cached = next((m for m in models if m.provider == provider and m.label == model_label), None)
        if cached is None:
            return _vision_from_fallback(provider, model_label)
        try:
            raw = json.loads(cached.raw_json)
        except (json.JSONDecodeError, TypeError):
            return _vision_from_fallback(provider, model_label)

    if not isinstance(raw, dict):
        return _vision_from_fallback(provider, model_label)

    if provider == "openrouter":
        arch = raw.get("architecture")
        if isinstance(arch, dict):
            modalities = arch.get("input_modalities")
            if isinstance(modalities, list):
                return "image" in modalities
        modalities = raw.get("modalities") or raw.get("input_modalities")
        if isinstance(modalities, list):
            return "image" in modalities
        return _vision_from_fallback(provider, model_label)

    if provider == "groq":
        modalities = raw.get("capabilities") or raw.get("modalities") or raw.get("input_modalities")
        if isinstance(modalities, list):
            return "image" in modalities or "vision" in modalities
        return _vision_from_fallback(provider, model_label)

    if provider == "openai-sub":
        capabilities = raw.get("capabilities") or raw.get("modalities")
        if isinstance(capabilities, list):
            return "vision" in capabilities or "image" in capabilities
        return _vision_from_fallback(provider, model_label)

    return False


def _vision_from_fallback(provider: str, model_label: str) -> bool:
    """Check known vision model lists when metadata is unavailable."""
    label_lower = model_label.lower()
    if provider == "groq":
        return model_label in GROQ_VISION_MODELS or "vision" in label_lower or "llava" in label_lower
    if provider == "openai-sub":
        return model_label in OPENAI_SUB_VISION_MODELS or "gpt-4o" in label_lower or "vision" in label_lower
    if provider == "openrouter":
        return (
            "vision" in label_lower
            or "image" in label_lower
            or "gemini" in label_lower
            or "claude-3" in label_lower
            or "claude-4" in label_lower
            or "gpt-4o" in label_lower
            or "gpt-4-vision" in label_lower
        )
    return False
