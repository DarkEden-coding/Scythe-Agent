from __future__ import annotations

from app.preprocessors.base import PreprocessorContext
from app.providers.base import LLMProvider

DEFAULT_SYSTEM_PROMPT = """You are a helpful AI coding assistant in an agentic workflow.

PATH CONVENTIONS: All paths in tool calls (read_file, edit_file, list_files, execute_command) are resolved relative to the selected project root—not the Scythe-Agent app directory. Always use relative paths from the project root (e.g. src/main.py, package/index.ts, README.md). Never use absolute paths like /Users/... or paths from this app's codebase.

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
        if ctx.messages and ctx.messages[0].get("role") == "system":
            ctx.messages[0]["content"] = prompt
        else:
            ctx.messages.insert(0, {"role": "system", "content": prompt})
        return ctx
