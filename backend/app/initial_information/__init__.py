"""Initial information: functions that augment chat messages with context."""

import inspect
from collections.abc import Callable

from app.initial_information.project_overview import (
    PROJECT_OVERVIEW_MAX_DEPTH,
    PROJECT_OVERVIEW_TOKEN_TARGET,
    add_project_overview_3_levels,
)

_ENHANCERS: list[Callable[..., list[dict]]] = [add_project_overview_3_levels]


def apply_initial_information(
    messages: list[dict],
    *,
    project_path: str | None = None,
    model: str | None = None,
    max_depth: int = PROJECT_OVERVIEW_MAX_DEPTH,
    token_target: int = PROJECT_OVERVIEW_TOKEN_TARGET,
) -> list[dict]:
    """
    Run all registered enhancers to add context to the message list.

    Args:
        messages: Chat messages (will be copied; not mutated in place).
        project_path: Path to the current project root, if available.
        model: Optional model id for tokenizer selection.
        max_depth: Maximum directory depth for project overview injection.
        token_target: Token target for injected overview sizing.

    Returns:
        New message list with any enhancer-added content.
    """
    result = list(messages)
    for enhancer in _ENHANCERS:
        try:
            params = inspect.signature(enhancer).parameters
            kwargs: dict[str, object] = {}
            if "project_path" in params:
                kwargs["project_path"] = project_path
            if "model" in params:
                kwargs["model"] = model
            if "max_depth" in params:
                kwargs["max_depth"] = max_depth
            if "token_target" in params:
                kwargs["token_target"] = token_target
            result = enhancer(result, **kwargs)
        except Exception:
            pass
    return result
