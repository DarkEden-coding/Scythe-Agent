"""Runs a stripped-down agent loop for sub-agents spawned by spawn_sub_agent."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.initial_information.project_overview import add_project_overview_3_levels
from app.services.llm_streamer import LLMStreamer
from app.tools.openrouter_format import get_openrouter_tools
from app.tools.registry import get_tool_registry
from app.utils.ids import generate_id
from app.utils.json_helpers import safe_parse_json
from app.utils.time import utc_now_iso
from app.utils.todos import normalize_todo_items

logger = logging.getLogger(__name__)

SUB_AGENT_EXCLUDED_TOOLS = {"spawn_sub_agent"}


@dataclass
class SubAgentRunResult:
    """Result of a sub-agent run."""

    output_text: str
    status: str  # completed | cancelled | error | max_iterations
    duration_ms: int
    tool_calls: list[dict]


class SubAgentRunner:
    """Runs a sub-agent loop: fresh conversation, filtered tools, lower iteration cap."""

    def __init__(
        self,
        *,
        chat_repo,
        project_repo,
        settings_repo,
        settings_service,
        api_key_resolver,
        event_bus,
        get_openrouter_tools_fn=None,
        default_system_prompt: str,
    ):
        self._chat_repo = chat_repo
        self._project_repo = project_repo
        self._settings_repo = settings_repo
        self._settings_service = settings_service
        self._api_key_resolver = api_key_resolver
        self._event_bus = event_bus
        self._get_openrouter_tools = get_openrouter_tools_fn or get_openrouter_tools
        self._default_system_prompt = default_system_prompt

    async def run(
        self,
        *,
        chat_id: str,
        sub_agent_id: str,
        tool_call_id: str,
        task: str,
        context_hint: str | None,
        project_path: str | None,
        model: str,
        model_provider: str | None,
        max_iterations: int,
    ) -> SubAgentRunResult:
        """Run the sub-agent loop and return aggregated output."""
        start_ts = datetime.now(timezone.utc)
        client = self._api_key_resolver.create_client(model_provider or "openrouter")
        if not client or not self._api_key_resolver.resolve(model_provider or "openrouter"):
            output = "No API key configured for sub-agent model."
            await self._publish_end(
                chat_id, sub_agent_id, tool_call_id, "error", output, start_ts
            )
            return SubAgentRunResult(
                output_text=output,
                status="error",
                duration_ms=int((datetime.now(timezone.utc) - start_ts).total_seconds() * 1000),
                tool_calls=[],
            )

        tools = self._get_openrouter_tools(exclude_names=SUB_AGENT_EXCLUDED_TOOLS)
        user_content = task
        if context_hint and context_hint.strip():
            user_content = f"{task}\n\nContext from parent: {context_hint.strip()}"

        messages: list[dict] = [
            {"role": "system", "content": self._default_system_prompt},
            {
                "role": "system",
                "content": self._sub_agent_iteration_guardrails(max_iterations=max_iterations),
            },
            {"role": "user", "content": user_content},
        ]
        messages = add_project_overview_3_levels(
            messages,
            project_path=project_path,
            model=model,
        )

        streamer = LLMStreamer(self._chat_repo, self._event_bus)
        registry = get_tool_registry()
        tool_calls_collected: list[dict] = []
        sub_agent_todos: list[dict] = []
        last_assistant_text = ""
        last_iteration_text = ""
        settings = self._settings_service.get_settings()
        reasoning_param = self._reasoning_param_for_settings(settings)

        try:
            for iteration in range(1, max_iterations + 1):
                msg_id = generate_id("msg")
                ts = utc_now_iso()
                rb_id = generate_id("rb")

                await self._event_bus.publish(
                    chat_id,
                    {
                        "type": "sub_agent_progress",
                        "payload": {
                            "subAgentId": sub_agent_id,
                            "iteration": iteration,
                            "message": f"Iteration {iteration}",
                        },
                    },
                )

                result = await streamer.stream_completion(
                    client=client,
                    model=model,
                    messages=messages,
                    tools=tools if tools else None,
                    reasoning_param=reasoning_param,
                    chat_id=chat_id,
                    msg_id=msg_id,
                    ts=ts,
                    checkpoint_id=None,
                    reasoning_block_id=rb_id,
                    silent=True,
                )
                response_text = result.text
                has_content = bool((response_text or result.finish_content or "").strip())

                if has_content:
                    final_text = (response_text or result.finish_content or "").strip()
                    response_text = final_text
                    last_assistant_text = final_text
                last_iteration_text = response_text or ""

                if result.finish_reason == "stop" or not result.tool_calls:
                    remaining_iterations = max(0, max_iterations - iteration)
                    messages.append({"role": "assistant", "content": response_text or ""})
                    messages.append(
                        {
                            "role": "user",
                            "content": self._sub_agent_completion_reminder(
                                remaining_iterations=remaining_iterations,
                                max_iterations=max_iterations,
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
                }
                messages.append(assistant_msg)

                tool_results: list[dict] = []
                for tc in result.tool_calls:
                    tc_id = tc.get("id", "")
                    fn = tc.get("function", {}) or {}
                    tc_name = fn.get("name", "unknown")
                    tc_args_str = fn.get("arguments", "{}")
                    tc_input = safe_parse_json(tc_args_str)

                    tc_out = {
                        "id": tc_id,
                        "name": tc_name,
                        "input": tc_input or {},
                        "status": "running",
                    }
                    await self._event_bus.publish(
                        chat_id,
                        {
                            "type": "sub_agent_tool_call",
                            "payload": {
                                "subAgentId": sub_agent_id,
                                "toolCall": tc_out,
                                "toolCallId": tc_id,
                            },
                        },
                    )

                    output = ""
                    tool_err: Exception | None = None
                    tool_ok = True
                    try:
                        local_handled, local_output, local_ok = (
                            self._run_local_sub_agent_tool(
                                tool_name=tc_name,
                                payload=tc_input if isinstance(tc_input, dict) else {},
                                todos=sub_agent_todos,
                            )
                        )
                        if local_handled:
                            output = local_output
                            tool_ok = local_ok
                        else:
                            tool = registry.get_tool(tc_name)
                            if tool is None:
                                output = f"Tool not found: {tc_name}"
                                tool_ok = False
                            else:
                                res = await tool.run(
                                    payload=tc_input or {},
                                    project_root=project_path,
                                    chat_id=chat_id,
                                    chat_repo=self._chat_repo,
                                )
                                output = res.output or ""
                                tool_ok = bool(res.ok)
                                if not res.ok:
                                    output = output or "Tool reported failure"
                    except Exception as e:
                        tool_err = e
                        tool_ok = False
                        output = str(e)
                        logger.warning(
                            "Sub-agent tool %s failed: %s", tc_name, e, exc_info=True
                        )

                    tc_out["status"] = (
                        "completed" if (tool_err is None and tool_ok) else "error"
                    )
                    tc_out["output"] = output
                    tool_calls_collected.append(tc_out)

                    await self._event_bus.publish(
                        chat_id,
                        {
                            "type": "sub_agent_tool_call",
                            "payload": {
                                "subAgentId": sub_agent_id,
                                "toolCall": tc_out,
                                "toolCallId": tc_id,
                            },
                        },
                    )

                    tool_results.append(
                        {"role": "tool", "tool_call_id": tc_id, "content": output}
                    )
                    if tc_name == "submit_task" and tool_ok and "Task submitted" in (output or ""):
                        duration_ms = int(
                            (datetime.now(timezone.utc) - start_ts).total_seconds() * 1000
                        )
                        output_text = last_assistant_text or response_text or "Sub-task completed."
                        await self._publish_end(
                            chat_id, sub_agent_id, tool_call_id, "completed", output_text, start_ts
                        )
                        return SubAgentRunResult(
                            output_text=output_text,
                            status="completed",
                            duration_ms=duration_ms,
                            tool_calls=tool_calls_collected,
                        )

                for tr in tool_results:
                    messages.append(tr)

            duration_ms = int(
                (datetime.now(timezone.utc) - start_ts).total_seconds() * 1000
            )
            last_visible_text = last_assistant_text or last_iteration_text or "(none)"
            output_text = (
                "Sub-agent reached iteration limit before calling submit_task. "
                f"Last assistant message: {last_visible_text}"
            )
            await self._publish_end(
                chat_id, sub_agent_id, tool_call_id, "max_iterations", output_text, start_ts
            )
            return SubAgentRunResult(
                output_text=output_text,
                status="max_iterations",
                duration_ms=duration_ms,
                tool_calls=tool_calls_collected,
            )

        except Exception as e:
            duration_ms = int(
                (datetime.now(timezone.utc) - start_ts).total_seconds() * 1000
            )
            output_text = f"Sub-agent error: {e}"
            logger.exception("Sub-agent run failed: %s", sub_agent_id)
            await self._publish_end(
                chat_id, sub_agent_id, tool_call_id, "error", output_text, start_ts
            )
            return SubAgentRunResult(
                output_text=output_text,
                status="error",
                duration_ms=duration_ms,
                tool_calls=tool_calls_collected,
            )
        except asyncio.CancelledError:
            output_text = "Sub-agent cancelled."
            await self._publish_end(
                chat_id, sub_agent_id, tool_call_id, "cancelled", output_text, start_ts
            )
            raise

    def _run_local_sub_agent_tool(
        self,
        *,
        tool_name: str,
        payload: dict,
        todos: list[dict],
    ) -> tuple[bool, str, bool]:
        """Handle tools with sub-agent local state to isolate from parent chat state."""
        if tool_name == "update_todo_list":
            items = payload.get("todos")
            if not isinstance(items, list):
                return True, "todos must be an array", False
            normalized = normalize_todo_items(items)
            todos.clear()
            todos.extend(normalized)
            return True, f"Todo list updated with {len(normalized)} item(s).", True

        if tool_name == "submit_task":
            incomplete = [t for t in todos if (t.get("status") or "").lower() != "completed"]
            if incomplete:
                return (
                    True,
                    (
                        "Todo list has incomplete items. Verify everything is done, use "
                        "update_todo_list to mark all items as completed, then call submit_task again."
                    ),
                    False,
                )
            return True, "Task submitted.", True

        return False, "", False

    async def _publish_end(
        self,
        chat_id: str,
        sub_agent_id: str,
        tool_call_id: str,
        status: str,
        output: str,
        start_ts: datetime,
    ) -> None:
        """Publish sub_agent_end event."""
        duration_ms = int(
            (datetime.now(timezone.utc) - start_ts).total_seconds() * 1000
        )
        await self._event_bus.publish(
            chat_id,
            {
                "type": "sub_agent_end",
                "payload": {
                    "subAgentId": sub_agent_id,
                    "toolCallId": tool_call_id,
                    "status": status,
                    "output": output,
                    "duration": duration_ms,
                },
            },
        )

    def _reasoning_param_for_settings(self, settings) -> dict | None:
        """Resolve reasoning param for model metadata; returns None if unsupported."""
        from app.services.agent_loop import AgentLoop

        return AgentLoop._reasoning_param_for_settings(settings)

    @staticmethod
    def _sub_agent_iteration_guardrails(*, max_iterations: int) -> str:
        """Build dynamic guidance that helps sub-agents budget tool usage."""
        return (
            "SUB-AGENT ITERATION BUDGET: "
            f"You have a hard cap of {max_iterations} iterations for this sub-task. "
            "Budget tool usage tightly: batch independent reads in parallel, avoid redundant "
            "or exploratory calls, and take direct actions that move the task to completion. "
            "Call submit_task as soon as the requested output is complete."
        )

    @staticmethod
    def _sub_agent_completion_reminder(
        *, remaining_iterations: int, max_iterations: int
    ) -> str:
        """Nudge the model to finish before exhausting iterations."""
        reminder = (
            f"You have {remaining_iterations} iteration(s) remaining out of {max_iterations}. "
            "You must call the submit_task tool when all tasks are complete. "
            "Avoid optional or repetitive tool calls."
        )
        if remaining_iterations <= 2:
            reminder += " You are near the cap, so prioritize finishing now."
        return reminder
