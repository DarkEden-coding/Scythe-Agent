"""Get file structure tool — tree-sitter-based outline with declarations and line ranges."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.types import ToolExecutionResult
from app.tools.path_utils import resolve_path
from app.utils.file_structure import get_file_structure


async def _handler(payload: dict, context: ToolExecutionContext) -> ToolExecutionResult:
    """Return file structure (declarations with 1-based line ranges) for use with read_file spans."""
    try:
        path = resolve_path(
            payload.get("path", ""),
            project_root=context.project_root,
            allow_external=True,
        )
    except ValueError as exc:
        return ToolExecutionResult(output=str(exc), file_edits=[], ok=False)
    if not path.exists() or not path.is_file():
        return ToolExecutionResult(output=f"File not found: {path}", file_edits=[], ok=False)

    def _read_structure(p: Path) -> str:
        content = p.read_text(encoding="utf-8")
        return get_file_structure(content, str(p))

    output = await asyncio.to_thread(_read_structure, path)
    return ToolExecutionResult(output=output, file_edits=[])


TOOL_PLUGIN = ToolPlugin(
    name="get_file_structure",
    description=(
        "Get the structure of a file (classes, functions, declarations) with 1-based line ranges. "
        "Use this before read_file to decide which line spans to read. Supports 50+ languages: "
        "Python, JS/TS, Go, Rust, Java, C/C++, C#, PHP, Swift, Kotlin, Scala, Ruby, Lua, Bash, Dart, "
        "Zig, R, Haskell, Julia, Elixir, Erlang, Nim, Clojure, F#, OCaml, Solidity, SQL, HTML/CSS, "
        "Vue, Svelte, Astro, GraphQL, Prisma, HCL/Terraform, Nix, Markdown, Make, CMake, Dockerfile, etc. "
        " path must be absolute. After getting structure, call read_file with start and end for specific sections."
    ),
    input_schema={
        "type": "object",
        "required": ["path"],
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file."},
        },
    },
    approval_policy="rules",
    handler=_handler,
)
