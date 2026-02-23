"""Centralized context/memory/overflow manager."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.output_spillover import spill_tool_output
from app.capabilities.memory.strategies import get_memory_strategy
from app.initial_information import apply_initial_information
from app.services.memory import MemoryConfig
from app.services.token_counter import count_messages_tokens

_ENV_BLOCK_PATTERN = re.compile(
    r"\n*<environment_details>[\s\S]*?</environment_details>\s*",
    re.IGNORECASE,
)


def _stable_compaction_split_index(messages: list[dict], recent_count: int) -> int:
    """Pick a split index that does not start the retained window with tool output."""
    split_idx = max(0, len(messages) - recent_count)
    while split_idx > 0 and messages[split_idx].get("role") == "tool":
        split_idx -= 1
    return split_idx


@dataclass
class ContextBudgetResult:
    messages: list[dict]
    estimated_tokens: int
    metadata: dict = field(default_factory=dict)


class ContextBudgetManager:
    def __init__(self, chat_repo, settings_repo) -> None:
        self._chat_repo = chat_repo
        self._settings_repo = settings_repo

    def _inject_system_prompt(self, messages: list[dict], prompt: str) -> list[dict]:
        out = list(messages)
        first = out[0] if out else None
        if first is None or first.get("role") != "system" or first.get("content") != prompt:
            out.insert(0, {"role": "system", "content": prompt})
        return out

    def _inject_todos(self, chat_id: str, messages: list[dict]) -> list[dict]:
        todos = self._chat_repo.get_current_todos(chat_id)
        out = list(messages)
        last_user_idx = None
        for i in range(len(out) - 1, -1, -1):
            if out[i].get("role") == "user":
                last_user_idx = i
                break
        if last_user_idx is None:
            return out

        content = out[last_user_idx].get("content") or ""
        content = _ENV_BLOCK_PATTERN.sub("", content)
        if todos:
            lines = [
                "<environment_details>",
                "REMINDERS",
                "",
                "Current reminders for this task:",
                "",
                "| # | Content | Status |",
                "|---|---------|--------|",
            ]
            for i, t in enumerate(todos, 1):
                status = str(t["status"]).replace("_", " ").title()
                item = str(t["content"] or "").replace("|", "\\|")[:80]
                if len(str(t["content"] or "")) > 80:
                    item += "..."
                lines.append(f"| {i} | {item} | {status} |")
            lines.extend(
                [
                    "",
                    "IMPORTANT: call `update_todo_list` whenever task status changes.",
                    "When done, call `submit_task` to end the agent loop.",
                    "</environment_details>",
                ]
            )
            content = content.rstrip() + "\n\n" + "\n".join(lines)
        out[last_user_idx] = {**out[last_user_idx], "content": content}
        return out

    def _apply_tool_output_spillover(
        self,
        messages: list[dict],
        project_id: str,
        model: str,
    ) -> list[dict]:
        """Spill oversized tool outputs to temp files; replace with first+last 50 lines."""
        out: list[dict] = []
        for msg in messages:
            if msg.get("role") == "tool" and isinstance(msg.get("content"), str):
                content = msg["content"]
                preview, _, _ = spill_tool_output(
                    content,
                    project_id,
                    model=model,
                )
                if preview != content:
                    msg = {**msg, "content": preview}
            out.append(msg)
        return out

    async def _compact_if_needed(
        self,
        *,
        messages: list[dict],
        provider,
        model: str,
        context_limit: int,
        threshold_ratio: float,
    ) -> tuple[list[dict], dict]:
        tokens = count_messages_tokens(messages, model=model)
        if tokens < int(context_limit * threshold_ratio):
            return messages, {"compaction_applied": False}

        recent_count = 4
        if len(messages) <= recent_count:
            return messages, {"compaction_applied": False}

        split_idx = _stable_compaction_split_index(messages, recent_count)
        old_messages = messages[:split_idx]
        recent_messages = messages[split_idx:]
        if not old_messages:
            return messages, {"compaction_applied": False}
        try:
            summary = await provider.create_chat_completion(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Summarize the following conversation history concisely. "
                            "Preserve key decisions, file paths, and tool results.\n\n"
                            + "\n".join(
                                f"[{m['role']}]: {str(m.get('content', ''))[:500]}"
                                for m in old_messages
                            )
                        ),
                    }
                ],
                max_tokens=512,
                temperature=0.0,
            )
        except Exception:
            return messages, {"compaction_applied": False}

        compacted = [{"role": "system", "content": f"[Conversation summary]: {summary}"}] + recent_messages
        return compacted, {
            "compaction_applied": True,
            "compacted_message_count": len(old_messages),
        }

    async def prepare(
        self,
        *,
        chat_id: str,
        base_messages: list[dict],
        default_system_prompt: str,
        project_path: str | None,
        provider,
        model: str,
        context_limit: int,
    ) -> ContextBudgetResult:
        metadata: dict = {}
        mem_cfg = MemoryConfig.from_settings_repo(self._settings_repo)

        messages = self._inject_system_prompt(base_messages, default_system_prompt)
        messages = self._inject_todos(chat_id, messages)
        messages = apply_initial_information(messages, project_path=project_path)
        chat = self._chat_repo.get_chat(chat_id)
        project_id = chat.project_id if chat else ""
        messages = self._apply_tool_output_spillover(messages, project_id, model)

        strategy = get_memory_strategy(mem_cfg.mode)
        mem_result = await strategy.build_context(
            chat_id=chat_id,
            messages=messages,
            chat_repo=self._chat_repo,
        )
        messages = mem_result.messages
        metadata.update(mem_result.metadata)

        # First token pass after pruning + memory.
        tokens_after_memory = count_messages_tokens(messages, model=model)
        metadata["tokens_after_memory"] = tokens_after_memory

        if mem_cfg.mode == "observational":
            metadata.update({
                "compaction_applied": False,
                "compaction_skipped": "observational_memory",
            })
        else:
            messages, compact_meta = await self._compact_if_needed(
                messages=messages,
                provider=provider,
                model=model,
                context_limit=context_limit,
                threshold_ratio=0.95,
            )
            metadata.update(compact_meta)

        # Final token pass.
        estimated_tokens = count_messages_tokens(messages, model=model)
        metadata["estimated_tokens"] = estimated_tokens
        metadata["memory_mode"] = mem_cfg.mode

        return ContextBudgetResult(
            messages=messages,
            estimated_tokens=estimated_tokens,
            metadata=metadata,
        )
