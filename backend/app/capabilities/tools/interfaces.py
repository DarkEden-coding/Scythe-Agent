from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, Protocol

from app.capabilities.tools.types import ToolExecutionResult

ApprovalPolicy = Literal["always", "rules", "manual"]


@dataclass
class ToolExecutionContext:
    project_root: str | None = None
    chat_id: str | None = None
    chat_repo: Any | None = None
    checkpoint_id: str | None = None
    tool_call_id: str | None = None


class ToolHandler(Protocol):
    def __call__(
        self,
        payload: dict,
        context: ToolExecutionContext,
    ) -> Awaitable[ToolExecutionResult]: ...


@dataclass
class ToolPlugin:
    """Single-file tool plugin contract (export as TOOL_PLUGIN)."""

    name: str
    description: str
    input_schema: dict
    approval_policy: ApprovalPolicy
    handler: Callable[[dict, ToolExecutionContext], Awaitable[ToolExecutionResult]]
    source: str = "builtin"
