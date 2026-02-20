"""Reasoning-capability helpers shared across providers and runtime."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

CANONICAL_REASONING_LEVELS = ("minimal", "low", "medium", "high")
OFF_REASONING_VALUES = {"off", "none", "disable", "disabled"}

_LEVEL_ALIASES = {
    "min": "minimal",
    "minimum": "minimal",
    "minimal": "minimal",
    "low": "low",
    "med": "medium",
    "medium": "medium",
    "default": "medium",
    "normal": "medium",
    "high": "high",
    "max": "high",
}

_REASONING_LEVEL_KEY_NAMES = {
    "reasoninglevel",
    "reasoninglevels",
    "reasoningeffort",
    "reasoningefforts",
    "supportedreasoninglevels",
    "supportedreasoningefforts",
    "allowedreasoninglevels",
    "allowedreasoningefforts",
}

_REASONING_HINT_KEY_NAMES = {
    "level",
    "levels",
    "effort",
    "efforts",
    "enum",
    "values",
    "options",
    "choices",
    "allowed",
    "supported",
}

_DEFAULT_REASONING_KEY_NAMES = {
    "defaultreasoninglevel",
    "defaultreasoningeffort",
    "reasoningdefaultlevel",
    "reasoningdefaulteffort",
}

_SUPPORT_REASONING_KEY_NAMES = {
    "reasoning",
    "reasoningsupported",
    "supportsreasoning",
    "supportsreasoningeffort",
    "reasoningeffort",
    "reasoningenabled",
}


@dataclass(frozen=True)
class ReasoningCapabilities:
    supported: bool
    levels: tuple[str, ...]
    default_level: str | None = None


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _normalize_level_token(
    value: str | None,
    *,
    allow_off: bool = False,
    allow_unknown: bool = False,
) -> str | None:
    if value is None:
        return None
    token = str(value).strip().lower()
    if not token:
        return None
    token = token.replace(" ", "_").replace("-", "_")
    if token in OFF_REASONING_VALUES:
        return "off" if allow_off else None
    if token in _LEVEL_ALIASES:
        return _LEVEL_ALIASES[token]
    if allow_unknown and re.fullmatch(r"[a-z0-9_]{1,32}", token):
        return token
    return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _order_levels(levels: list[str]) -> list[str]:
    unique = set(_dedupe(levels))
    ordered = [level for level in CANONICAL_REASONING_LEVELS if level in unique]
    extras = sorted(unique - set(CANONICAL_REASONING_LEVELS))
    return ordered + extras


def _extract_levels_from_string(value: str) -> list[str]:
    direct = _normalize_level_token(value, allow_off=False, allow_unknown=False)
    if direct:
        return [direct]
    parts = re.split(r"[,\s|/]+", value.strip())
    out: list[str] = []
    for part in parts:
        level = _normalize_level_token(part, allow_off=False, allow_unknown=False)
        if level:
            out.append(level)
    return out


def _extract_levels_direct(value: Any) -> list[str]:
    if isinstance(value, str):
        return _extract_levels_from_string(value)

    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                for key_name in ("id", "name", "value", "level", "effort"):
                    if key_name in item:
                        out.extend(_extract_levels_direct(item[key_name]))
            else:
                out.extend(_extract_levels_direct(item))
        return out

    if isinstance(value, dict):
        out: list[str] = []
        for key_name in (
            "enum",
            "values",
            "levels",
            "efforts",
            "supported",
            "allowed",
            "options",
            "choices",
            "value",
        ):
            if key_name in value:
                out.extend(_extract_levels_direct(value[key_name]))
        return out

    return []


def _collect_levels(value: Any, *, reasoning_context: bool = False) -> list[str]:
    if isinstance(value, dict):
        out: list[str] = []
        for raw_key, child in value.items():
            key = _normalize_key(str(raw_key))
            child_reasoning_context = reasoning_context or ("reasoning" in key)

            if key in _REASONING_LEVEL_KEY_NAMES:
                out.extend(_extract_levels_direct(child))
            elif child_reasoning_context and key in _REASONING_HINT_KEY_NAMES:
                out.extend(_extract_levels_direct(child))

            if isinstance(child, (dict, list, tuple, set)):
                out.extend(
                    _collect_levels(child, reasoning_context=child_reasoning_context)
                )
        return out

    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            out.extend(_collect_levels(item, reasoning_context=reasoning_context))
        if reasoning_context:
            out.extend(_extract_levels_direct(list(value)))
        return out

    if reasoning_context:
        return _extract_levels_direct(value)
    return []


def _find_default_level(value: Any, *, reasoning_context: bool = False) -> str | None:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = _normalize_key(str(raw_key))
            child_reasoning_context = reasoning_context or ("reasoning" in key)

            if key in _DEFAULT_REASONING_KEY_NAMES:
                parsed = _extract_levels_direct(child)
                if parsed:
                    return parsed[0]

            if child_reasoning_context and key == "default":
                parsed = _extract_levels_direct(child)
                if parsed:
                    return parsed[0]

            default_from_child = _find_default_level(
                child, reasoning_context=child_reasoning_context
            )
            if default_from_child:
                return default_from_child
        return None

    if isinstance(value, (list, tuple, set)):
        for item in value:
            default_from_item = _find_default_level(
                item, reasoning_context=reasoning_context
            )
            if default_from_item:
                return default_from_item
    return None


def _contains_reasoning_signal(value: Any) -> bool:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = _normalize_key(str(raw_key))
            if key in _SUPPORT_REASONING_KEY_NAMES:
                if isinstance(child, bool):
                    if child:
                        return True
                elif child not in (None, "", 0, False, [], {}):
                    return True

            if key in {"supportedparameters", "supportedfeatures", "capabilities"}:
                if isinstance(child, (list, tuple, set)):
                    for item in child:
                        if isinstance(item, str):
                            low = item.lower()
                            if "reasoning" in low or "reasoning_effort" in low:
                                return True

            if _contains_reasoning_signal(child):
                return True
        return False

    if isinstance(value, (list, tuple, set)):
        for item in value:
            if _contains_reasoning_signal(item):
                return True
        return False

    return False


def _provider_default_levels(provider: str, model_label: str) -> tuple[str, ...]:
    provider_id = provider.strip().lower()
    label = model_label.strip().lower()

    # GPT-5 / o-series generally support "minimal" alongside low/medium/high.
    if re.search(r"(gpt[-_]?5)|(^|[^a-z0-9])o[13]([^a-z0-9]|$)", label):
        return ("minimal", "low", "medium", "high")

    if provider_id in {"openrouter", "groq", "openai-sub"}:
        return ("low", "medium", "high")

    return ()


def _heuristic_reasoning_support(provider: str, model_label: str) -> bool:
    provider_id = provider.strip().lower()
    label = model_label.strip().lower()

    if provider_id == "openai-sub":
        return bool(re.search(r"(gpt[-_]?5)|(^|[^a-z0-9])o[13]([^a-z0-9]|$)", label))

    return bool(
        re.search(
            r"(gpt[-_]?5)|(^|[^a-z0-9])o[13]([^a-z0-9]|$)|"
            r"(^|[^a-z0-9])r1([^a-z0-9]|$)|reason",
            label,
        )
    )


def extract_reasoning_capabilities(
    *,
    provider: str,
    model_label: str,
    raw_model: dict[str, Any] | None,
) -> ReasoningCapabilities:
    payload = raw_model if isinstance(raw_model, dict) else {}
    levels = _order_levels(_collect_levels(payload))
    supported = bool(levels)

    if not supported and _contains_reasoning_signal(payload):
        supported = True
    if not supported and _heuristic_reasoning_support(provider, model_label):
        supported = True

    if supported and not levels:
        levels = list(_provider_default_levels(provider, model_label))

    default_level = _find_default_level(payload)
    if default_level not in levels:
        if "medium" in levels:
            default_level = "medium"
        elif levels:
            default_level = levels[0]
        else:
            default_level = None

    return ReasoningCapabilities(
        supported=supported,
        levels=tuple(levels),
        default_level=default_level,
    )


def normalize_reasoning_setting(value: str | None) -> str:
    normalized = _normalize_level_token(
        value, allow_off=True, allow_unknown=True
    )
    if not normalized:
        raise ValueError("Invalid reasoning level")
    return normalized


def resolve_reasoning_effort(
    *,
    requested_level: str | None,
    available_levels: list[str] | tuple[str, ...],
    default_level: str | None = None,
) -> str | None:
    normalized_request = _normalize_level_token(
        requested_level, allow_off=True, allow_unknown=True
    )
    if normalized_request in (None, "off"):
        return None

    normalized_levels = _dedupe(
        [
            level
            for raw in available_levels
            if (level := _normalize_level_token(raw, allow_unknown=True))
        ]
    )
    if not normalized_levels:
        return None

    if normalized_request in normalized_levels:
        return normalized_request

    normalized_default = _normalize_level_token(
        default_level, allow_off=False, allow_unknown=True
    )
    if normalized_default and normalized_default in normalized_levels:
        return normalized_default

    if "medium" in normalized_levels:
        return "medium"

    return normalized_levels[0]
