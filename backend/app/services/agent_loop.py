"""Orchestrates the full agent loop using LLMStreamer and ToolExecutor."""

from __future__ import annotations

import logging

from app.preprocessors.auto_compaction import AutoCompactionPreprocessor
from app.preprocessors.pipeline import PreprocessorPipeline
from app.preprocessors.system_prompt import SystemPromptPreprocessor
from app.preprocessors.token_estimator import TokenEstimatorPreprocessor
from app.preprocessors.tool_result_pruner import ToolResultPrunerPreprocessor
from app.preprocessors.base import PreprocessorContext
from app.schemas.chat import MessageOut
from app.services.llm_streamer import LLMStreamer
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
        apply_initial_information,
        get_openrouter_tools,
        default_system_prompt: str,
    ):
        self._chat_repo = chat_repo
        self._project_repo = project_repo
        self._settings_repo = settings_repo
        self._settings_service = settings_service
        self._api_key_resolver = api_key_resolver
        self._approval_svc = approval_svc
        self._event_bus = event_bus
        self._apply_initial_information = apply_initial_information
        self._get_openrouter_tools = get_openrouter_tools
        self._default_system_prompt = default_system_prompt

    async def run(
        self,
        *,
        chat_id: str,
        checkpoint_id: str,
        content: str,
        max_iterations: int,
    ) -> None:
        client = self._api_key_resolver.create_client()
        if not client or not self._api_key_resolver.resolve():
            await self._event_bus.publish(
                chat_id,
                {
                    "type": "message",
                    "payload": {
                        "message": {
                            "id": generate_id("msg"),
                            "role": "agent",
                            "content": "No API key configured. Add your OpenRouter API key in settings to get agent responses.",
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
        openrouter_messages = self._apply_initial_information(
            openrouter_messages, project_path=project_path
        )
        tools = self._get_openrouter_tools()
        pipeline = PreprocessorPipeline(
            [
                SystemPromptPreprocessor(default_prompt=self._default_system_prompt),
                TokenEstimatorPreprocessor(),
                ToolResultPrunerPreprocessor(),
                AutoCompactionPreprocessor(threshold_ratio=0.85),
            ]
        )
        context_limit = settings.contextLimit

        streamer = LLMStreamer(self._chat_repo, self._event_bus)
        executor = ToolExecutor(self._chat_repo, self._approval_svc, self._event_bus)

        msg_id = generate_id("msg")
        ts = utc_now_iso()
        message_out = MessageOut(
            id=msg_id,
            role="agent",
            content="",
            timestamp=ts,
            checkpointId=None,
        )
        await self._event_bus.publish(
            chat_id,
            {"type": "message", "payload": {"message": message_out.model_dump()}},
        )

        iteration = 0
        reasoning_param = {"effort": "medium"}
        response_chunks: list[str] = []

        while iteration < max_iterations:
            iteration += 1
            ctx = PreprocessorContext(
                chat_id=chat_id,
                messages=list(openrouter_messages),
                model=settings.model,
                context_limit=context_limit,
            )
            ctx = await pipeline.run(ctx, client)
            openrouter_messages = ctx.messages

            result = await streamer.stream_completion(
                client=client,
                model=settings.model,
                messages=openrouter_messages,
                tools=tools if tools else None,
                reasoning_param=reasoning_param,
                chat_id=chat_id,
                msg_id=msg_id,
                ts=ts,
                checkpoint_id=checkpoint_id,
            )
            response_chunks.append(result.text)
            response_text = result.text

            if result.finish_reason == "stop" or not result.tool_calls:
                final_text = (
                    (response_text or result.finish_content or "").strip()
                    or "(No response generated)"
                )
                self._finalize_message(
                    chat_id, msg_id, ts, final_text, chat_model, message_out
                )
                await self._event_bus.publish(
                    chat_id,
                    {"type": "message", "payload": {"message": message_out.model_dump()}},
                )
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
            }
            openrouter_messages.append(assistant_msg)

            tool_results = await executor.execute_tool_calls(
                tool_calls_from_stream=result.tool_calls,
                chat_id=chat_id,
                checkpoint_id=checkpoint_id,
            )
            for tr in tool_results:
                openrouter_messages.append(tr)

        final_text = (
            "".join(response_chunks).strip() if response_chunks else ""
        ) or "(Agent reached max iterations)"
        self._finalize_message(
            chat_id, msg_id, ts, final_text, chat_model, message_out
        )
        await self._event_bus.publish(
            chat_id,
            {"type": "message", "payload": {"message": message_out.model_dump()}},
        )
        await self._event_bus.publish(
            chat_id,
            {"type": "agent_done", "payload": {"checkpointId": checkpoint_id}},
        )

    def _assemble_messages(self, chat_id: str, content: str) -> list[dict]:
        """Assemble messages without system prompt; SystemPromptPreprocessor adds it."""
        messages = self._chat_repo.list_messages(chat_id)
        openrouter_messages: list[dict] = []
        for m in messages:
            role = "assistant" if m.role == "assistant" else "user"
            openrouter_messages.append({"role": role, "content": m.content})
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
