"""Static model metadata for OpenAI subscription-backed models."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

OPENAI_SUB_MODEL_SCHEMA: dict[str, dict[str, Any]] = {
    "gpt-5.1-codex-max": {
        "maxTokens": 128_000,
        "contextWindow": 400_000,
        "includedTools": ["apply_patch"],
        "excludedTools": ["apply_diff", "write_to_file"],
        "supportsImages": True,
        "supportsPromptCache": True,
        "supportsReasoningEffort": ["low", "medium", "high", "xhigh"],
        "reasoningEffort": "xhigh",
        "inputPrice": 0,
        "outputPrice": 0,
        "supportsTemperature": False,
        "description": "GPT-5.1 Codex Max: Maximum capability coding model via ChatGPT subscription",
    },
    "gpt-5.1-codex": {
        "maxTokens": 128_000,
        "contextWindow": 400_000,
        "includedTools": ["apply_patch"],
        "excludedTools": ["apply_diff", "write_to_file"],
        "supportsImages": True,
        "supportsPromptCache": True,
        "supportsReasoningEffort": ["low", "medium", "high"],
        "reasoningEffort": "medium",
        "inputPrice": 0,
        "outputPrice": 0,
        "supportsTemperature": False,
        "description": "GPT-5.1 Codex: GPT-5.1 optimized for agentic coding via ChatGPT subscription",
    },
    "gpt-5.3-codex": {
        "maxTokens": 128_000,
        "contextWindow": 400_000,
        "includedTools": ["apply_patch"],
        "excludedTools": ["apply_diff", "write_to_file"],
        "supportsImages": True,
        "supportsPromptCache": True,
        "supportsReasoningEffort": ["low", "medium", "high", "xhigh"],
        "reasoningEffort": "medium",
        "inputPrice": 0,
        "outputPrice": 0,
        "supportsTemperature": False,
        "description": "GPT-5.3 Codex: OpenAI's flagship coding model via ChatGPT subscription",
    },
    "gpt-5.3-codex-spark": {
        "maxTokens": 8_192,
        "contextWindow": 128_000,
        "includedTools": ["apply_patch"],
        "excludedTools": ["apply_diff", "write_to_file"],
        "supportsImages": False,
        "supportsPromptCache": True,
        "supportsReasoningEffort": ["low", "medium", "high", "xhigh"],
        "reasoningEffort": "medium",
        "inputPrice": 0,
        "outputPrice": 0,
        "supportsTemperature": False,
        "description": "GPT-5.3 Codex Spark: Fast, text-only coding model via ChatGPT subscription",
    },
    "gpt-5.2-codex": {
        "maxTokens": 128_000,
        "contextWindow": 400_000,
        "includedTools": ["apply_patch"],
        "excludedTools": ["apply_diff", "write_to_file"],
        "supportsImages": True,
        "supportsPromptCache": True,
        "supportsReasoningEffort": ["low", "medium", "high", "xhigh"],
        "reasoningEffort": "medium",
        "inputPrice": 0,
        "outputPrice": 0,
        "supportsTemperature": False,
        "description": "GPT-5.2 Codex: OpenAI's flagship coding model via ChatGPT subscription",
    },
    "gpt-5.1": {
        "maxTokens": 128_000,
        "contextWindow": 400_000,
        "includedTools": ["apply_patch"],
        "excludedTools": ["apply_diff", "write_to_file"],
        "supportsImages": True,
        "supportsPromptCache": True,
        "supportsReasoningEffort": ["none", "low", "medium", "high"],
        "reasoningEffort": "medium",
        "inputPrice": 0,
        "outputPrice": 0,
        "supportsVerbosity": True,
        "supportsTemperature": False,
        "description": "GPT-5.1: General GPT-5.1 model via ChatGPT subscription",
    },
    "gpt-5": {
        "maxTokens": 128_000,
        "contextWindow": 400_000,
        "includedTools": ["apply_patch"],
        "excludedTools": ["apply_diff", "write_to_file"],
        "supportsImages": True,
        "supportsPromptCache": True,
        "supportsReasoningEffort": ["minimal", "low", "medium", "high"],
        "reasoningEffort": "medium",
        "inputPrice": 0,
        "outputPrice": 0,
        "supportsVerbosity": True,
        "supportsTemperature": False,
        "description": "GPT-5: General GPT-5 model via ChatGPT subscription",
    },
    "gpt-5-codex": {
        "maxTokens": 128_000,
        "contextWindow": 400_000,
        "includedTools": ["apply_patch"],
        "excludedTools": ["apply_diff", "write_to_file"],
        "supportsImages": True,
        "supportsPromptCache": True,
        "supportsReasoningEffort": ["low", "medium", "high"],
        "reasoningEffort": "medium",
        "inputPrice": 0,
        "outputPrice": 0,
        "supportsTemperature": False,
        "description": "GPT-5 Codex: GPT-5 optimized for agentic coding via ChatGPT subscription",
    },
    "gpt-5-codex-mini": {
        "maxTokens": 128_000,
        "contextWindow": 400_000,
        "includedTools": ["apply_patch"],
        "excludedTools": ["apply_diff", "write_to_file"],
        "supportsImages": True,
        "supportsPromptCache": True,
        "supportsReasoningEffort": ["low", "medium", "high"],
        "reasoningEffort": "medium",
        "inputPrice": 0,
        "outputPrice": 0,
        "supportsTemperature": False,
        "description": "GPT-5 Codex Mini: Faster coding model via ChatGPT subscription",
    },
    "gpt-5.1-codex-mini": {
        "maxTokens": 128_000,
        "contextWindow": 400_000,
        "includedTools": ["apply_patch"],
        "excludedTools": ["apply_diff", "write_to_file"],
        "supportsImages": True,
        "supportsPromptCache": True,
        "supportsReasoningEffort": ["low", "medium", "high"],
        "reasoningEffort": "medium",
        "inputPrice": 0,
        "outputPrice": 0,
        "supportsTemperature": False,
        "description": "GPT-5.1 Codex Mini: Faster version for coding tasks via ChatGPT subscription",
    },
    "gpt-5.4": {
        "maxTokens": 128_000,
        "contextWindow": 1_050_000,
        "includedTools": ["apply_patch"],
        "excludedTools": ["apply_diff", "write_to_file"],
        "supportsImages": True,
        "supportsPromptCache": True,
        "supportsReasoningEffort": ["none", "low", "medium", "high", "xhigh"],
        "reasoningEffort": "none",
        "inputPrice": 0,
        "outputPrice": 0,
        "supportsVerbosity": True,
        "supportsTemperature": False,
        "description": "GPT-5.4: Most capable model via ChatGPT subscription",
    },
    "gpt-5.2": {
        "maxTokens": 128_000,
        "contextWindow": 400_000,
        "includedTools": ["apply_patch"],
        "excludedTools": ["apply_diff", "write_to_file"],
        "supportsImages": True,
        "supportsPromptCache": True,
        "supportsReasoningEffort": ["none", "low", "medium", "high", "xhigh"],
        "reasoningEffort": "medium",
        "inputPrice": 0,
        "outputPrice": 0,
        "supportsTemperature": False,
        "description": "GPT-5.2: Latest GPT model via ChatGPT subscription",
    },
}


OPENAI_SUB_MODELS: tuple[dict[str, Any], ...] = tuple(
    {"id": model_id, **deepcopy(spec)}
    for model_id, spec in OPENAI_SUB_MODEL_SCHEMA.items()
)


def get_openai_sub_model(model_id: str) -> dict[str, Any] | None:
    spec = OPENAI_SUB_MODEL_SCHEMA.get(model_id)
    if spec is None:
        return None
    return {"id": model_id, **deepcopy(spec)}


def get_openai_sub_model_ids() -> list[str]:
    return [str(model["id"]) for model in OPENAI_SUB_MODELS]


def get_openai_sub_models_payload() -> list[dict[str, Any]]:
    return [deepcopy(model) for model in OPENAI_SUB_MODELS]
