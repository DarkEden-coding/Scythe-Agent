"""Orchestrates the full agent loop using LLMStreamer and ToolExecutor."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.capabilities.context_budget.manager import ContextBudgetManager
from app.providers.reasoning import resolve_reasoning_effort
from app.capabilities.memory.strategies import get_memory_strategy
from app.schemas.chat import MessageOut
from app.services.llm_streamer import LLMStreamer
from app.services.memory import MemoryConfig
from app.services.tool_executor import ToolExecutor
from app.providers.vision import model_has_vision
from app.utils.json_helpers import safe_parse_json
from app.utils.ids import generate_id
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)
REPETITIVE_TOOL_CALL_STREAK_LIMIT = 5
_MENTION_INPUT_FLAG = "__mention_reference__"
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
        has_vision = model_has_vision(
            provider, settings.model, self._settings_repo
        )
        vp_settings = self._settings_repo.get_vision_preprocessor_settings()
        vision_preprocessor = None
        if vp_settings.get("vision_preprocessor_model") and not has_vision:
            vision_preprocessor = {
                "model": vp_settings["vision_preprocessor_model"],
                "provider": vp_settings.get("vision_preprocessor_model_provider")
                or self._settings_repo.get_provider_for_model(
                    vp_settings["vision_preprocessor_model"]
                )
                or "openrouter",
            }
        conversation_messages = await self._assemble_messages(
            chat_id,
            content,
            model_has_vision=has_vision,
            vision_preprocessor=vision_preprocessor,
        )
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

    _VISION_PREPROCESSOR_TIMEOUT = 90.0
    _VISION_PREPROCESSOR_CACHE_VERSION = "v2"

    async def _summarize_images_with_vision_model(
        self,
        *,
        attachments: list,
        preprocessor_model: str,
        preprocessor_provider: str,
        user_message: str = "",
    ) -> str:
        """Call vision preprocessor model to describe images. Returns detailed summary."""
        if not attachments:
            return ""
        vp_client = self._api_key_resolver.create_client(preprocessor_provider)
        if not vp_client or not self._api_key_resolver.resolve(preprocessor_provider):
            return f"[{len(attachments)} image(s) - vision preprocessor API key not configured]"
        if user_message and user_message.strip():
            prompt = (
                "The user sent these images with the following message. Provide a detailed analysis:\n\n"
                f"User message: {user_message.strip()}\n\n"
                "For each image:\n"
                "1. Give a thorough visual description (text, diagrams, UI elements, layout, colors, important details).\n"
                "2. Emphasize and elaborate on anything directly relevant to what the user is asking about.\n"
                "Be comprehensive so a text-only model can fully address the user's question."
            )
        else:
            prompt = (
                "Describe these images in detail for a text-only model. "
                "Include any visible text, diagrams, UI elements, layout, colors, and important visual details. "
                "Provide one thorough description per image."
            )
        parts: list[dict] = [{"type": "text", "text": prompt}]
        for att in attachments:
            data_url = f"data:{att.mime_type};base64,{att.content_base64}"
            parts.append({"type": "image_url", "image_url": {"url": data_url}})
        vp_messages = [{"role": "user", "content": parts}]
        logger.info(
            "Vision preprocessor: summarizing %d image(s) with model=%s (provider=%s)",
            len(attachments),
            preprocessor_model,
            preprocessor_provider,
        )
        try:
            text = await asyncio.wait_for(
                vp_client.create_chat_completion(
                    model=preprocessor_model,
                    messages=vp_messages,
                    max_tokens=2048,
                    temperature=0.3,
                ),
                timeout=self._VISION_PREPROCESSOR_TIMEOUT,
            )
            return (text or "").strip()
        except asyncio.TimeoutError:
            logger.warning(
                "Vision preprocessor timed out after %.0fs for model=%s",
                self._VISION_PREPROCESSOR_TIMEOUT,
                preprocessor_model,
            )
            return ""
        except Exception as exc:
            logger.warning(
                "Vision preprocessor failed for model=%s: %s",
                preprocessor_model,
                exc,
                exc_info=True,
            )
            return ""

    async def _assemble_messages(
        self,
        chat_id: str,
        content: str,
        *,
        model_has_vision: bool = False,
        vision_preprocessor: dict | None = None,
    ) -> list[dict]:
        """Assemble messages without system prompt; SystemPromptPreprocessor adds it."""
        messages = self._chat_repo.list_messages(chat_id)
        referenced_files_by_checkpoint: dict[str, list[str]] = {}
        for tc in self._chat_repo.list_tool_calls(chat_id):
            if not tc.checkpoint_id or tc.name != "read_file":
                continue
            payload = safe_parse_json(tc.input_json)
            if not bool(payload.get(_MENTION_INPUT_FLAG)):
                continue
            path = str(payload.get("path", "")).strip()
            if not path:
                continue
            bucket = referenced_files_by_checkpoint.setdefault(tc.checkpoint_id, [])
            if path not in bucket:
                bucket.append(path)
        openrouter_messages: list[dict] = []
        for m in messages:
            role = "assistant" if m.role == "assistant" else "user"
            content_text = m.content or ""
            if role == "user" and m.checkpoint_id:
                ref_paths = referenced_files_by_checkpoint.get(m.checkpoint_id, [])
                if ref_paths:

                    def _replace_file_placeholder(match: re.Match[str], paths: list[str] = ref_paths) -> str:
                        idx = int(match.group(1))
                        return Path(paths[idx]).name if 0 <= idx < len(paths) else match.group(0)

                    content_text = re.sub(r"\{\{FILE:(\d+)\}\}\}*", _replace_file_placeholder, content_text)
                    refs_inline = " ".join(
                        f"<File reference: {path} do not re-read file>" for path in ref_paths
                    )
                    content_text = (
                        f"{content_text}\n{refs_inline}" if content_text else refs_inline
                    )
            msg_content: str | list[dict]
            if role == "user" and model_has_vision:
                attachments = self._chat_repo.list_attachments_for_message(m.id)
                if attachments:
                    parts: list[dict] = []
                    if content_text:
                        parts.append({"type": "text", "text": content_text})
                    for att in attachments:
                        data_url = f"data:{att.mime_type};base64,{att.content_base64}"
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        })
                    msg_content = parts
                else:
                    msg_content = content_text
            else:
                if role == "user":
                    attachments = self._chat_repo.list_attachments_for_message(m.id)
                    if attachments and not model_has_vision:
                        if vision_preprocessor:
                            summary = getattr(m, "image_summarization", None) or ""
                            summary_model = getattr(m, "image_summarization_model", None)
                            expected_key = (
                                f"{vision_preprocessor['model']}:{self._VISION_PREPROCESSOR_CACHE_VERSION}"
                            )
                            if not summary or summary_model != expected_key:
                                await self._event_bus.publish(
                                    chat_id,
                                    {
                                        "type": "vision_preprocessing",
                                        "payload": {
                                            "imageCount": len(attachments),
                                            "message": "Summarizing images...",
                                        },
                                    },
                                )
                                summary = await self._summarize_images_with_vision_model(
                                    attachments=attachments,
                                    preprocessor_model=vision_preprocessor["model"],
                                    preprocessor_provider=vision_preprocessor["provider"],
                                    user_message=content_text,
                                )
                                if summary:
                                    self._chat_repo.update_message_image_summarization(
                                        m.id, summary, expected_key
                                    )
                                    self._chat_repo.commit()
                                    logger.info(
                                        "Vision preprocessor: persisted summarization for message=%s",
                                        m.id,
                                    )
                            image_block = (
                                f"\n\n--- Image descriptions ---\n{summary}\n\n"
                                "[Do not use read_file to read the image(s) - refer to the "
                                "descriptions above.]"
                                if summary
                                else f"\n\n[Vision preprocessor failed to describe {len(attachments)} image(s).]"
                            )
                            content_text = (
                                f"{content_text}{image_block}" if content_text else image_block.lstrip()
                            )
                        else:
                            content_text = (
                                f"{content_text}\n[{len(attachments)} image(s) attached - "
                                "model does not support vision]"
                                if content_text
                                else f"[{len(attachments)} image(s) attached - model does not support vision]"
                            )
                msg_content = content_text
            openrouter_messages.append({
                "role": role,
                "content": msg_content,
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
