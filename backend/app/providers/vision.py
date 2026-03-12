"""Vision capability detection for LLM models."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, Optional, Protocol

from app.providers.openai_sub.models import get_openai_sub_model


class _SettingsRepo(Protocol):
    """Protocol for repositories used by vision model metadata lookup."""

    def list_models(self) -> Iterable[Any]:
        ...

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

def model_has_vision(
    provider: str,
    model_label: str,
    settings_repo: _SettingsRepo,
    raw_model: Optional[dict] = None,
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
        supports_images = raw.get("supportsImages")
        if isinstance(supports_images, bool):
            return supports_images
        capabilities = raw.get("capabilities") or raw.get("modalities") or raw.get("input_modalities")
        if isinstance(capabilities, list):
            normalized = {str(cap).lower() for cap in capabilities}
            if "vision" in normalized or "image" in normalized:
                return True
            if normalized:
                return False
        known_model = get_openai_sub_model(model_label)
        if known_model is not None:
            supports_images = known_model.get("supportsImages")
            if isinstance(supports_images, bool):
                return supports_images
        return True

    return False


def _vision_from_fallback(provider: str, model_label: str) -> bool:
    """Check known vision model lists when metadata is unavailable."""
    label_lower = model_label.lower()
    if provider == "groq":
        return model_label in GROQ_VISION_MODELS or "vision" in label_lower or "llava" in label_lower
    if provider == "openai-sub":
        known_model = get_openai_sub_model(model_label)
        if known_model is not None:
            supports_images = known_model.get("supportsImages")
            if isinstance(supports_images, bool):
                return supports_images
        return True
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
