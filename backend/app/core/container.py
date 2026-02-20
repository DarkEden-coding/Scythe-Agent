from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AppContainer:
    """App-scoped runtime container."""

    event_bus: Any
    tool_registry: Any
    om_runner: Any
    approval_waiter: Any
    agent_task_manager: Any
    mcp_client_manager: Any


_container: AppContainer | None = None


def set_container(container: AppContainer | None) -> None:
    global _container
    _container = container


def get_container() -> AppContainer | None:
    return _container
