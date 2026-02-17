"""Initial information: functions that augment chat messages with context."""

from app.initial_information.project_overview import add_project_overview_3_levels

_ENHANCERS: list[callable] = [add_project_overview_3_levels]


def apply_initial_information(
    messages: list[dict],
    *,
    project_path: str | None = None,
) -> list[dict]:
    """
    Run all registered enhancers to add context to the message list.

    Args:
        messages: Chat messages (will be copied; not mutated in place).
        project_path: Path to the current project root, if available.

    Returns:
        New message list with any enhancer-added content.
    """
    result = list(messages)
    for enhancer in _ENHANCERS:
        try:
            result = enhancer(result, project_path=project_path)
        except Exception:
            pass
    return result
