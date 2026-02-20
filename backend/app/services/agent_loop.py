"""Orchestrates the full agent loop using LLMStreamer and ToolExecutor."""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.capabilities.context_budget.manager import ContextBudgetManager
from app.capabilities.memory.strategies import get_memory_strategy
from app.schemas.chat import MessageOut
from app.services.llm_streamer import LLMStreamer
from app.services.memory import MemoryConfig
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
            return

        chat_model = self._chat_repo.get_chat(chat_id)
        if chat_model is None:
            await self._event_bus.publish(
                chat_id,
                {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
            )
            logger.info("Conversation ended: chat not found chat_id=%s", chat_id)
            return

        settings = self._settings_service.get_settings()
        conversation_messages = self._assemble_messages(chat_id, content)
        project_path = None
        project = self._project_repo.get_project(chat_model.project_id)
        if project:
            project_path = project.path
        tools = self._get_openrouter_tools()

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
        reasoning_param = {"effort": "medium"}
        _cancelled = False

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
                    default_system_prompt=self._default_system_prompt,
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
                    conversation_messages.append(
                        {"role": "assistant", "content": response_text or ""}
                    )
                    conversation_messages.append(
                        {
                            "role": "user",
                            "content": (
                                "You must call the submit_task tool when all tasks are complete. "
                                "The agent loop continues until you call submit_task."
                            ),
                        }
                    )
                    continue

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
                submit_task_succeeded = False
                for tr in tool_results:
                    if tc_id_to_name.get(tr.get("tool_call_id")) == "submit_task":
                        if (tr.get("content") or "").strip() == "Task submitted.":
                            submit_task_succeeded = True
                        break
                if submit_task_succeeded:
                    await self._event_bus.publish(
                        chat_id,
                        {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
                    )
                    logger.info(
                        "Conversation ended: submit_task succeeded chat_id=%s checkpoint_id=%s",
                        chat_id,
                        checkpoint_id,
                    )
                    return

                # Queue OM updates during long-running loops so threshold-triggered
                # observation does not depend on turn completion.
                if self._session_factory:
                    try:
                        strategy = get_memory_strategy(mem_cfg.mode)
                        strategy.maybe_update(
                            chat_id=chat_id,
                            model=settings.model,
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
            await self._event_bus.publish(
                chat_id,
                {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
            )
            logger.info(
                "Conversation ended: max iterations reached (iteration=%d) chat_id=%s checkpoint_id=%s",
                iteration,
                chat_id,
                checkpoint_id,
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
                        mem_cfg=mem_cfg,
                        client=client,
                        session_factory=self._session_factory,
                        event_bus=self._event_bus,
                    )
                except Exception:
                    logger.warning(
                        "Failed to schedule observation for chat=%s", chat_id, exc_info=True
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
