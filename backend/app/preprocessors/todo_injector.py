"""TodoInjectorPreprocessor — injects current todo list into the last user message."""

from __future__ import annotations

import re

from app.preprocessors.base import PreprocessorContext
from app.providers.base import LLMProvider

_ENV_BLOCK_PATTERN = re.compile(
    r"\n*<environment_details>[\s\S]*?</environment_details>\s*",
    re.IGNORECASE,
)


class TodoInjectorPreprocessor:
    """Append or replace REMINDERS block on the last user message with current todos.

    Runs at priority 12: after SystemPromptPreprocessor (10), before ProjectContextPreprocessor (15).
    """

    name = "todo_injector"
    priority = 12

    def __init__(self, chat_repo) -> None:
        self._chat_repo = chat_repo

    async def process(
        self,
        ctx: PreprocessorContext,
        provider: LLMProvider,
    ) -> PreprocessorContext:
        chat_id = ctx.chat_id
        todos = self._chat_repo.list_todos(chat_id)

        last_user_idx = None
        for i in range(len(ctx.messages) - 1, -1, -1):
            if ctx.messages[i].get("role") == "user":
                last_user_idx = i
                break
        if last_user_idx is None:
            return ctx

        content = ctx.messages[last_user_idx].get("content") or ""
        content = _ENV_BLOCK_PATTERN.sub("", content)

        if todos:
            lines = [
                "<environment_details>",
                "REMINDERS",
                "",
                "Below is your current list of reminders for this task. Keep them updated as you progress.",
                "",
                "| # | Content | Status |",
                "|---|---------|--------|",
            ]
            for i, t in enumerate(todos, 1):
                status = t.status.replace("_", " ").title()
                content_escaped = (t.content or "").replace("|", "\\|")[:80]
                if len(t.content or "") > 80:
                    content_escaped += "..."
                lines.append(f"| {i} | {content_escaped} | {status} |")
            lines.append("")
            lines.append(
                "IMPORTANT: When task status changes, remember to call the `update_todo_list` tool to update your progress."
            )
            lines.append("</environment_details>")
            content = content.rstrip() + "\n\n" + "\n".join(lines)
        ctx.messages[last_user_idx] = {
            **ctx.messages[last_user_idx],
            "content": content,
        }
        return ctx
