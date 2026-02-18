from __future__ import annotations

from app.preprocessors.base import PreprocessorContext
from app.providers.base import LLMProvider

DEFAULT_SYSTEM_PROMPT = """You are a helpful AI coding assistant in an agentic workflow.

PATH CONVENTIONS: All paths in tool calls (read_file, edit_file, list_files, execute_command cwd) must be absolute paths. The project root is provided in the project overview—use it to build paths (e.g. /path/to/project/src/main.py). Never use relative paths (e.g. src/main.py). Never use paths from the Scythe-Agent app codebase.

READ_FILE BEHAVIOR: Call read_file without start/end to get the file structure (outline with line ranges) and total line count. Supported formats include code (.py, .ts, .js, etc.) and config (.toml, .json, .yaml, .yml). Use the structure to decide which spans to read, then call read_file with start and end (1-based line numbers) for specific sections. For unsupported extensions or when structure is unavailable, use read_file with start and end directly. Always prefer targeted spans over reading entire large files.

PARALLEL TOOL CALLS: Prefer issuing multiple independent tool calls in a single turn when they can run in parallel (e.g. reading several files at once, listing directories while grepping). This reduces latency and speeds up tasks. Only serialize calls when one depends on another's output.

WORKFLOW: The user may need to approve tool calls before they run. Prefer small, focused operations. Explain your reasoning when making changes. Use list_files to explore the project structure before reading or editing."""


class SystemPromptPreprocessor:
    """Inject system prompt at the start of the message list."""

    name = "system_prompt"
    priority = 10

    def __init__(self, default_prompt: str = DEFAULT_SYSTEM_PROMPT):
        self._default_prompt = default_prompt

    async def process(
        self,
        ctx: PreprocessorContext,
        provider: LLMProvider,
    ) -> PreprocessorContext:
        prompt = ctx.system_prompt or self._default_prompt
        first = ctx.messages[0] if ctx.messages else None
        if first is None or first.get("role") != "system" or first.get("content") != prompt:
            ctx.messages.insert(0, {"role": "system", "content": prompt})
        return ctx
