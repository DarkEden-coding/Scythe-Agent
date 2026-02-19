from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ToolFileEdit:
    file_path: str
    action: str
    diff: str | None = None
    original_content: str | None = None


@dataclass
class ToolResult:
    output: str
    file_edits: list[ToolFileEdit]
    ok: bool = True


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict

    async def run(
        self,
        payload: dict,
        *,
        project_root: str | None = None,
        chat_id: str | None = None,
        chat_repo=None,
    ) -> ToolResult: ...
