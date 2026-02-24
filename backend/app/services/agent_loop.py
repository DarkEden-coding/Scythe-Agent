"""Orchestrates the full agent loop using LLMStreamer and ToolExecutor."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

import httpx

from app.capabilities.context_budget.manager import ContextBudgetManager
from app.providers.reasoning import resolve_reasoning_effort
from app.capabilities.memory.strategies import get_memory_strategy
from app.schemas.chat import MessageOut
from app.services.llm_streamer import LLMStreamer
from app.services.memory import MemoryConfig
from app.services.tool_executor import ToolExecutor
from app.utils.ids import generate_id
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)
REPETITIVE_TOOL_CALL_STREAK_LIMIT = 5
GUARDED_REPEAT_TOOLS = {"read_file", "list_files", "grep"}
PLANNING_ALLOWED_TOOLS = {
    "list_files",
    "read_file",
    "grep",
    "spawn_sub_agent",
    "update_todo_list",
    "submit_task",
    "user_query",
}
PLANNING_PROMPT_APPENDIX = """
PLANNING MODE:
- You are in planning mode. Do not modify project files or run shell commands.
- You may explore with read-only tools and sub-agents when needed.
- Use spawn_sub_agent adaptively: only when scope is broad (for example more than 6 candidate files or multiple top-level modules).
- Produce a detailed markdown implementation plan.
- Include file-by-file changes, code snippets, and test commands with expected outcomes per step.
- Include rollback notes for risky steps.
- End with the final markdown plan.
"""
PLAN_EDIT_PROMPT_APPENDIX = """
PLAN EDIT MODE:
- Update the existing plan based on the user's edit request.
- Prefer targeted section edits and keep unaffected sections stable.
- Return updated plan markdown only.
"""


@dataclass
class AgentRunResult:
    completed: bool
    iterations: int
    final_assistant_text: str
    mode: str


class AgentLoop:
    """Runs the agent loop: message assembly, stream, tool execution, loop until stop."""

    def __init__(
        self,
        *,
        chat_repo,
        project_repo,
        settings_repo,
        settings_service,
        api_key_resolver,
        approval_svc,
        event_bus,
        get_openrouter_tools,
        default_system_prompt: str,
        session_factory=None,
    ):
        self._chat_repo = chat_repo
        self._project_repo = project_repo
        self._settings_repo = settings_repo
        self._settings_service = settings_service
        self._api_key_resolver = api_key_resolver
        self._approval_svc = approval_svc
        self._event_bus = event_bus
        self._get_openrouter_tools = get_openrouter_tools
        self._default_system_prompt = default_system_prompt
        self._session_factory = session_factory

    @staticmethod
    def _model_metadata_for_settings(settings) -> dict | None:
        model_key = settings.modelKey
        if not model_key and settings.modelProvider:
            model_key = f"{settings.modelProvider}::{settings.model}"
        if model_key and settings.modelMetadataByKey:
            by_key = settings.modelMetadataByKey.get(model_key)
            if by_key:
                return by_key
        if settings.modelMetadata:
            by_label = settings.modelMetadata.get(settings.model)
            if by_label:
                return by_label
        return None

    @classmethod
    def _reasoning_param_for_settings(cls, settings) -> dict | None:
        meta = cls._model_metadata_for_settings(settings)
        if not meta:
            return None
        if isinstance(meta, dict):
            levels = list(meta.get("reasoningLevels") or [])
            default_level = meta.get("defaultReasoningLevel")
        else:
            levels = list(getattr(meta, "reasoningLevels", []) or [])
            default_level = getattr(meta, "defaultReasoningLevel", None)
        if not levels:
            return None
        selected = resolve_reasoning_effort(
            requested_level=getattr(settings, "reasoningLevel", None),
            available_levels=levels,
            default_level=default_level,
        )
        if not selected:
            return None
        return {"effort": selected}

    async def run(
        self,
        *,
        chat_id: str,
        checkpoint_id: str,
        content: str,
        max_iterations: int,
        mode: str = "default",
        extra_messages: list[dict] | None = None,
    ) -> AgentRunResult:
        mode_name = mode if mode in {"default", "planning", "plan_edit"} else "default"
        is_plan_mode = mode_name in {"planning", "plan_edit"}
        settings = self._settings_service.get_settings()
        provider = settings.modelProvider or self._settings_repo.get_provider_for_model(
            settings.model
        )
        if not provider:
            provider = "openrouter"
        client = self._api_key_resolver.create_client(provider)
        if not client or not self._api_key_resolver.resolve(provider):
            await self._event_bus.publish(
                chat_id,
                {
                    "type": "message",
                    "payload": {
                        "message": {
                            "id": generate_id("msg"),
                            "role": "agent",
                            "content": f"No {provider} API key configured. Add your API key in settings to get agent responses.",
                            "timestamp": utc_now_iso(),
                            "checkpointId": None,
                        }
                    },
                },
            )
            await self._event_bus.publish(
                chat_id,
                {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
            )
            logger.info(
                "Conversation ended: no API key configured for provider=%s chat_id=%s",
                provider,
                chat_id,
            )
            return AgentRunResult(
                completed=False,
                iterations=0,
                final_assistant_text="",
                mode=mode_name,
            )

        chat_model = self._chat_repo.get_chat(chat_id)
        if chat_model is None:
            await self._event_bus.publish(
                chat_id,
                {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
            )
            logger.info("Conversation ended: chat not found chat_id=%s", chat_id)
            return AgentRunResult(
                completed=False,
                iterations=0,
                final_assistant_text="",
                mode=mode_name,
            )

        settings = self._settings_service.get_settings()
        conversation_messages = self._assemble_messages(chat_id, content)
        if extra_messages:
            conversation_messages.extend(extra_messages)
        project_path = None
        project = self._project_repo.get_project(chat_model.project_id)
        if project:
            project_path = project.path
        tools = self._resolve_tools_for_mode(mode_name)

        # Load memory settings
        mem_cfg = MemoryConfig.from_settings_repo(self._settings_repo)

        context_budget = ContextBudgetManager(self._chat_repo, self._settings_repo)
        context_limit = settings.contextLimit

        streamer = LLMStreamer(self._chat_repo, self._event_bus)
        executor = ToolExecutor(
            self._chat_repo,
            self._approval_svc,
            self._event_bus,
            session_factory=self._session_factory,
        )

        iteration = 0
        reasoning_param = self._reasoning_param_for_settings(settings)
        _cancelled = False
        last_guard_signature: tuple[str, str] | None = None
        repeated_tool_streak = 0
        last_assistant_text = ""

        try:
            while iteration < max_iterations:
                iteration += 1
                msg_id = generate_id("msg")
                reasoning_block_id = generate_id("rb")
                ts = utc_now_iso()
                message_out = MessageOut(
                    id=msg_id,
                    role="agent",
                    content="",
                    timestamp=ts,
                    checkpointId=None,
                )

                prepared = await context_budget.prepare(
                    chat_id=chat_id,
                    base_messages=list(conversation_messages),
                    default_system_prompt=self._system_prompt_for_mode(mode_name),
                    project_path=project_path,
                    provider=client,
                    model=settings.model,
                    context_limit=context_limit,
                )
                llm_messages = prepared.messages

                rp = reasoning_param
                try:
                    result = await streamer.stream_completion(
                        client=client,
                        model=settings.model,
                        messages=llm_messages,
                        tools=tools if tools else None,
                        reasoning_param=rp,
                        chat_id=chat_id,
                        msg_id=msg_id,
                        ts=ts,
                        checkpoint_id=checkpoint_id,
                        reasoning_block_id=reasoning_block_id,
                        suppress_content_events=is_plan_mode,
                    )
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 400 and rp:
                        logger.warning(
                            "OpenRouter 400 with reasoning, retrying without reasoning for model=%s",
                            settings.model,
                        )
                        rp = None
                        result = await streamer.stream_completion(
                            client=client,
                            model=settings.model,
                            messages=llm_messages,
                            tools=tools if tools else None,
                            reasoning_param=rp,
                            chat_id=chat_id,
                            msg_id=msg_id,
                            ts=ts,
                            checkpoint_id=checkpoint_id,
                            reasoning_block_id=reasoning_block_id,
                            suppress_content_events=is_plan_mode,
                        )
                    else:
                        raise
                response_text = result.text
                final_text = (response_text or result.finish_content or "").strip()
                has_content = bool(final_text)
                terminal_response = result.finish_reason == "stop" or not result.tool_calls

                if has_content:
                    if not is_plan_mode or terminal_response:
                        last_assistant_text = final_text
                    should_publish_message = not is_plan_mode or not terminal_response
                    if should_publish_message:
                        self._finalize_message(
                            chat_id, msg_id, ts, final_text, chat_model, message_out
                        )
                        await self._event_bus.publish(
                            chat_id,
                            {"type": "message", "payload": {"message": message_out.model_dump()}},
                        )

                if terminal_response:
                    last_guard_signature = None
                    repeated_tool_streak = 0
                    if is_plan_mode:
                        await self._event_bus.publish(
                            chat_id,
                            {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
                        )
                        logger.info(
                            "Conversation ended: planning stop chat_id=%s checkpoint_id=%s mode=%s",
                            chat_id,
                            checkpoint_id,
                            mode_name,
                        )
                        return AgentRunResult(
                            completed=True,
                            iterations=iteration,
                            final_assistant_text=last_assistant_text,
                            mode=mode_name,
                        )
                    conversation_messages.append(
                        {"role": "assistant", "content": response_text or ""}
                    )
                    conversation_messages.append(
                        {
                            "role": "user",
                            "content": (
                                "You must call the submit_task tool when all tasks are complete, "
                                "or user_query when you need more information from the user. "
                                "The agent loop continues until you call one of these tools."
                            ),
                        }
                    )
                    continue

                for tc in result.tool_calls:
                    signature = self._loop_guard_signature(tc)
                    if signature is None:
                        last_guard_signature = None
                        repeated_tool_streak = 0
                        continue

                    tc_name, target = signature
                    if signature == last_guard_signature:
                        repeated_tool_streak += 1
                    else:
                        last_guard_signature = signature
                        repeated_tool_streak = 1

                    if repeated_tool_streak >= REPETITIVE_TOOL_CALL_STREAK_LIMIT:
                        await self._pause_for_repetitive_tool_loop(
                            chat_id=chat_id,
                            checkpoint_id=checkpoint_id,
                            chat_model=chat_model,
                            tool_name=tc_name,
                            target=target,
                            repeat_count=repeated_tool_streak,
                        )
                        return AgentRunResult(
                            completed=False,
                            iterations=iteration,
                            final_assistant_text=last_assistant_text,
                            mode=mode_name,
                        )

                assistant_msg = {
                    "role": "assistant",
                    "content": response_text or "",
                    "tool_calls": [
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": tc.get("function", {}).get("arguments", "{}"),
                            },
                        }
                        for tc in result.tool_calls
                    ],
                    "_message_id": msg_id,
                }
                conversation_messages.append(assistant_msg)

                tool_results = await executor.execute_tool_calls(
                    tool_calls_from_stream=result.tool_calls,
                    chat_id=chat_id,
                    checkpoint_id=checkpoint_id,
                )
                for tr in tool_results:
                    tr_with_id = dict(tr)
                    tr_with_id["_message_id"] = msg_id
                    conversation_messages.append(tr_with_id)

                tc_id_to_name = {
                    tc.get("id", ""): tc.get("function", {}).get("name", "")
                    for tc in result.tool_calls
                }
                loop_ended = False
                for tr in tool_results:
                    tc_name = tc_id_to_name.get(tr.get("tool_call_id"))
                    content = (tr.get("content") or "").strip()
                    if tc_name == "submit_task" and content == "Task submitted.":
                        loop_ended = True
                        logger.info(
                            "Conversation ended: submit_task succeeded chat_id=%s checkpoint_id=%s",
                            chat_id,
                            checkpoint_id,
                        )
                        break
                    if tc_name == "user_query" and content == "Awaiting user response.":
                        loop_ended = True
                        logger.info(
                            "Conversation ended: user_query awaiting response chat_id=%s checkpoint_id=%s",
                            chat_id,
                            checkpoint_id,
                        )
                        break
                if loop_ended:
                    await self._event_bus.publish(
                        chat_id,
                        {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
                    )
                    return AgentRunResult(
                        completed=True,
                        iterations=iteration,
                        final_assistant_text=last_assistant_text,
                        mode=mode_name,
                    )

                # Queue OM updates during long-running loops so threshold-triggered
                # observation does not depend on turn completion.
                if self._session_factory:
                    try:
                        strategy = get_memory_strategy(mem_cfg.mode)
                        strategy.maybe_update(
                            chat_id=chat_id,
                            model=settings.model,
                            project_path=project_path,
                            mem_cfg=mem_cfg,
                            client=client,
                            session_factory=self._session_factory,
                            event_bus=self._event_bus,
                        )
                    except Exception:
                        logger.warning(
                            "Failed mid-turn observation schedule for chat=%s",
                            chat_id,
                            exc_info=True,
                        )

            # Max iterations reached
            pause_message = (
                f"Agent paused after reaching the iteration cap ({max_iterations}) "
                "before calling submit_task."
            )
            await self._event_bus.publish(
                chat_id,
                {
                    "type": "agent_paused",
                    "payload": {
                        "reason": "max_iterations",
                        "checkpointId": checkpoint_id,
                        "iteration": iteration,
                        "maxIterations": max_iterations,
                        "message": pause_message,
                    },
                },
            )
            await self._event_bus.publish(
                chat_id,
                {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
            )
            logger.info(
                "Conversation ended: max iterations reached before submit_task (iteration=%d, max_iterations=%d) chat_id=%s checkpoint_id=%s",
                iteration,
                max_iterations,
                chat_id,
                checkpoint_id,
            )
            return AgentRunResult(
                completed=False,
                iterations=iteration,
                final_assistant_text=last_assistant_text,
                mode=mode_name,
            )
        except asyncio.CancelledError:
            _cancelled = True
            raise
        finally:
            # Schedule observation once after a non-cancelled run exit.
            # This covers normal completion and error exits that still produced
            # useful chat/tool history, while avoiding stale writes on user cancel.
            if not _cancelled and self._session_factory:
                try:
                    strategy = get_memory_strategy(mem_cfg.mode)
                    strategy.maybe_update(
                        chat_id=chat_id,
                        model=settings.model,
                        project_path=project_path,
                        mem_cfg=mem_cfg,
                        client=client,
                        session_factory=self._session_factory,
                        event_bus=self._event_bus,
                    )
                except Exception:
                    logger.warning(
                        "Failed to schedule observation for chat=%s", chat_id, exc_info=True
                    )

    def _resolve_tools_for_mode(self, mode: str) -> list[dict]:
        tools = self._get_openrouter_tools()
        if mode not in {"planning", "plan_edit"}:
            return tools
        filtered: list[dict] = []
        for spec in tools:
            fn = spec.get("function", {}) if isinstance(spec, dict) else {}
            tool_name = fn.get("name")
            if tool_name in PLANNING_ALLOWED_TOOLS:
                filtered.append(spec)
        return filtered

    def _system_prompt_for_mode(self, mode: str) -> str:
        if mode == "planning":
            return f"{self._default_system_prompt.rstrip()}\n\n{PLANNING_PROMPT_APPENDIX.strip()}"
        if mode == "plan_edit":
            return f"{self._default_system_prompt.rstrip()}\n\n{PLAN_EDIT_PROMPT_APPENDIX.strip()}"
        return self._default_system_prompt

    def _assemble_messages(self, chat_id: str, content: str) -> list[dict]:
        """Assemble messages without system prompt; SystemPromptPreprocessor adds it."""
        messages = self._chat_repo.list_messages(chat_id)
        openrouter_messages: list[dict] = []
        for m in messages:
            role = "assistant" if m.role == "assistant" else "user"
            openrouter_messages.append({
                "role": role,
                "content": m.content,
                "_message_id": m.id,
            })
        if not openrouter_messages:
            openrouter_messages = [{"role": "user", "content": content}]
        return openrouter_messages

    def _finalize_message(
        self,
        chat_id: str,
        msg_id: str,
        ts: str,
        final_text: str,
        chat_model,
        message_out: MessageOut,
    ) -> None:
        self._chat_repo.create_message(
            message_id=msg_id,
            chat_id=chat_id,
            role="assistant",
            content=final_text,
            timestamp=ts,
            checkpoint_id=None,
        )
        if chat_model:
            self._chat_repo.update_chat_timestamp(chat_model, ts)
        self._chat_repo.commit()
        message_out.content = final_text

    def _parse_tool_args(self, raw_args: object) -> dict:
        if isinstance(raw_args, dict):
            return raw_args
        if not isinstance(raw_args, str):
            return {}
        text = raw_args.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _loop_guard_signature(self, tool_call: dict) -> tuple[str, str] | None:
        """Build a strict repetition signature only for file/path-oriented read tools."""
        fn = tool_call.get("function", {}) or {}
        tool_name = fn.get("name", "unknown")
        if tool_name not in GUARDED_REPEAT_TOOLS:
            return None
        args = self._parse_tool_args(fn.get("arguments", "{}"))
        if tool_name == "read_file":
            path = str(args.get("path", "")).strip()
            if not path:
                return None
            return (tool_name, f"path={path}")
        if tool_name == "list_files":
            path = str(args.get("path", "")).strip()
            if not path:
                return None
            recursive = bool(args.get("recursive", False))
            return (tool_name, f"path={path}|recursive={recursive}")
        if tool_name == "grep":
            path = str(args.get("path", "")).strip()
            pattern = str(args.get("pattern", "")).strip()
            if not path or not pattern:
                return None
            return (tool_name, f"path={path}|pattern={pattern}")
        return None

    async def _pause_for_repetitive_tool_loop(
        self,
        *,
        chat_id: str,
        checkpoint_id: str,
        chat_model,
        tool_name: str,
        target: str,
        repeat_count: int,
    ) -> None:
        warning_text = (
            f"I paused because I called `{tool_name}` on the same target ({target}) "
            f"{repeat_count} times in a row. Tell me how you'd like to proceed."
        )
        msg_id = generate_id("msg")
        ts = utc_now_iso()
        message_out = MessageOut(
            id=msg_id,
            role="agent",
            content="",
            timestamp=ts,
            checkpointId=None,
        )
        self._finalize_message(
            chat_id=chat_id,
            msg_id=msg_id,
            ts=ts,
            final_text=warning_text,
            chat_model=chat_model,
            message_out=message_out,
        )
        await self._event_bus.publish(
            chat_id,
            {"type": "message", "payload": {"message": message_out.model_dump()}},
        )
        await self._event_bus.publish(
            chat_id,
            {
                "type": "agent_paused",
                "payload": {
                    "reason": "repetitive_tool_calls",
                    "checkpointId": checkpoint_id,
                    "toolName": tool_name,
                    "target": target,
                    "repeatCount": repeat_count,
                    "message": warning_text,
                },
            },
        )
        await self._event_bus.publish(
            chat_id,
            {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
        )
        logger.info(
            "Conversation ended: repetitive tool loop detected chat_id=%s checkpoint_id=%s tool=%s target=%s repeat_count=%d",
            chat_id,
            checkpoint_id,
            tool_name,
            target,
            repeat_count,
        )
