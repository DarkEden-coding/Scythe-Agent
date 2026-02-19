"""Orchestrates the full agent loop using LLMStreamer and ToolExecutor."""

from __future__ import annotations

import logging

import httpx

from app.preprocessors.auto_compaction import AutoCompactionPreprocessor
from app.preprocessors.base import PreprocessorContext
from app.preprocessors.observational_memory import ObservationalMemoryPreprocessor
from app.preprocessors.pipeline import PreprocessorPipeline
from app.preprocessors.project_context import ProjectContextPreprocessor
from app.preprocessors.system_prompt import SystemPromptPreprocessor
from app.preprocessors.token_estimator import TokenEstimatorPreprocessor
from app.preprocessors.tool_result_pruner import ToolResultPrunerPreprocessor
from app.schemas.chat import MessageOut
from app.services.llm_streamer import LLMStreamer
from app.services.memory import MemoryConfig
from app.services.memory.observational.background import om_runner
from app.services.memory.observational.service import ObservationMemoryService
from app.services.token_counter import count_messages_tokens
from app.services.tool_executor import ToolExecutor
from app.utils.ids import generate_id
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)


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
        # Kept for backward compatibility; project context is now a pipeline preprocessor
        apply_initial_information=None,
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

    async def run(
        self,
        *,
        chat_id: str,
        checkpoint_id: str,
        content: str,
        max_iterations: int,
    ) -> None:
        settings = self._settings_service.get_settings()
        provider = self._settings_repo.get_provider_for_model(settings.model)
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
            return

        chat_model = self._chat_repo.get_chat(chat_id)
        if chat_model is None:
            await self._event_bus.publish(
                chat_id,
                {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
            )
            return

        settings = self._settings_service.get_settings()
        openrouter_messages = self._assemble_messages(chat_id, content)
        project_path = None
        project = self._project_repo.get_project(chat_model.project_id)
        if project:
            project_path = project.path
        tools = self._get_openrouter_tools()

        # Load memory settings
        mem_cfg = MemoryConfig.from_settings_repo(self._settings_repo)

        # Build preprocessor pipeline
        memory_preprocessor: ObservationalMemoryPreprocessor | AutoCompactionPreprocessor
        if mem_cfg.mode == "observational":
            memory_preprocessor = ObservationalMemoryPreprocessor(self._chat_repo)
        else:
            memory_preprocessor = AutoCompactionPreprocessor(threshold_ratio=0.85)

        pipeline = PreprocessorPipeline(
            [
                SystemPromptPreprocessor(default_prompt=self._default_system_prompt),
                ProjectContextPreprocessor(project_path),   # priority 15: after system prompt
                TokenEstimatorPreprocessor(),
                ToolResultPrunerPreprocessor(),
                memory_preprocessor,
                # Always keep AutoCompaction as last-resort fallback at 95%
                AutoCompactionPreprocessor(threshold_ratio=0.95),
            ]
        )
        context_limit = settings.contextLimit

        streamer = LLMStreamer(self._chat_repo, self._event_bus)
        executor = ToolExecutor(
            self._chat_repo,
            self._approval_svc,
            self._event_bus,
            session_factory=self._session_factory,
        )

        iteration = 0
        reasoning_param = {"effort": "medium"}

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

            ctx = PreprocessorContext(
                chat_id=chat_id,
                messages=list(openrouter_messages),
                model=settings.model,
                context_limit=context_limit,
            )
            ctx = await pipeline.run(ctx, client)
            openrouter_messages = ctx.messages

            rp = reasoning_param
            try:
                result = await streamer.stream_completion(
                    client=client,
                    model=settings.model,
                    messages=openrouter_messages,
                    tools=tools if tools else None,
                    reasoning_param=rp,
                    chat_id=chat_id,
                    msg_id=msg_id,
                    ts=ts,
                    checkpoint_id=checkpoint_id,
                    reasoning_block_id=reasoning_block_id,
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
                        messages=openrouter_messages,
                        tools=tools if tools else None,
                        reasoning_param=rp,
                        chat_id=chat_id,
                        msg_id=msg_id,
                        ts=ts,
                        checkpoint_id=checkpoint_id,
                        reasoning_block_id=reasoning_block_id,
                    )
                else:
                    raise
            response_text = result.text
            has_content = bool((response_text or result.finish_content or "").strip())

            if has_content:
                final_text = (response_text or result.finish_content or "").strip()
                self._finalize_message(
                    chat_id, msg_id, ts, final_text, chat_model, message_out
                )
                await self._event_bus.publish(
                    chat_id,
                    {"type": "message", "payload": {"message": message_out.model_dump()}},
                )

            if result.finish_reason == "stop" or not result.tool_calls:
                if not has_content:
                    openrouter_messages.append(
                        {"role": "assistant", "content": response_text or ""}
                    )
                    openrouter_messages.append(
                        {
                            "role": "user",
                            "content": "You used no tools and provided no response. You must use tools for every response except your last response, which must have text content to the user.",
                        }
                    )
                    continue
                await self._event_bus.publish(
                    chat_id,
                    {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
                )
                return

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
            openrouter_messages.append(assistant_msg)

            tool_results = await executor.execute_tool_calls(
                tool_calls_from_stream=result.tool_calls,
                chat_id=chat_id,
                checkpoint_id=checkpoint_id,
            )
            for tr in tool_results:
                tr_with_id = dict(tr)
                tr_with_id["_message_id"] = msg_id
                openrouter_messages.append(tr_with_id)

            # After tool results: schedule background observation if OM is enabled
            if mem_cfg.mode == "observational" and self._session_factory:
                self._maybe_schedule_observation(
                    chat_id=chat_id,
                    messages=openrouter_messages,
                    model=settings.model,
                    observer_model=mem_cfg.observer_model,
                    reflector_model=mem_cfg.reflector_model,
                    observer_threshold=mem_cfg.observer_threshold,
                    reflector_threshold=mem_cfg.reflector_threshold,
                    client=client,
                )

        await self._event_bus.publish(
            chat_id,
            {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
        )

    def _maybe_schedule_observation(
        self,
        *,
        chat_id: str,
        messages: list[dict],
        model: str,
        observer_model: str | None,
        reflector_model: str | None,
        observer_threshold: int,
        reflector_threshold: int,
        client,
    ) -> None:
        """Schedule background observation if there are enough unobserved tokens."""
        latest_obs = self._chat_repo.get_latest_observation(chat_id)
        svc = ObservationMemoryService(self._chat_repo)
        _observed, unobserved = svc.get_unobserved_messages(messages, latest_obs)
        unobserved_tokens = count_messages_tokens(unobserved)

        if unobserved_tokens >= observer_threshold:
            om_runner.schedule_observation(
                chat_id=chat_id,
                messages=list(messages),
                model=model,
                observer_model=observer_model,
                reflector_model=reflector_model,
                observer_threshold=observer_threshold,
                reflector_threshold=reflector_threshold,
                client=client,
                session_factory=self._session_factory,
                event_bus=self._event_bus,
            )

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
