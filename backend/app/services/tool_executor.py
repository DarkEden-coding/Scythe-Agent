"""Encapsulates tool call handling (auto-approve vs manual-approve flow)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.chat import ToolCallOut
from app.services.approval_waiter import register_and_wait
from app.utils.json_helpers import safe_parse_json
from app.utils.time import utc_now_iso


class ToolExecutor:
    """Handles tool call execution with approval flow."""

    def __init__(self, chat_repo, approval_svc, event_bus):
        self._chat_repo = chat_repo
        self._approval_svc = approval_svc
        self._event_bus = event_bus

    async def execute_tool_calls(
        self,
        *,
        tool_calls_from_stream: list[dict],
        chat_id: str,
        checkpoint_id: str,
    ) -> list[dict]:
        """Execute tool calls; return tool result messages for conversation."""
        tool_results: list[dict] = []
        for tc in tool_calls_from_stream:
            tc_id = tc.get("id", "")
            fn = tc.get("function", {}) or {}
            tc_name = fn.get("name", "unknown")
            tc_args_str = fn.get("arguments", "{}")
            tc_input = safe_parse_json(tc_args_str)
            tc_db_id = tc_id if tc_id.startswith("tc-") else f"tc-{tc_id}"

            auto_approved = self._approval_svc.should_auto_approve(
                tc_name, tc_input or {}
            )
            if auto_approved:
                self._chat_repo.create_tool_call(
                    tool_call_id=tc_db_id,
                    chat_id=chat_id,
                    checkpoint_id=checkpoint_id,
                    name=tc_name,
                    status="pending",
                    input_json=tc_args_str,
                    timestamp=utc_now_iso(),
                )
                self._chat_repo.commit()
                await self._event_bus.publish(
                    chat_id,
                    {
                        "type": "tool_call_start",
                        "payload": {
                            "toolCall": {
                                "id": tc_db_id,
                                "name": tc_name,
                                "status": "running",
                                "input": tc_input,
                                "timestamp": utc_now_iso(),
                                "checkpointId": checkpoint_id,
                            }
                        },
                    },
                )
                try:
                    tool_out, _ = await self._approval_svc.approve(
                        chat_id=chat_id, tool_call_id=tc_db_id
                    )
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": tool_out.output or "",
                        }
                    )
                except Exception as exc:
                    tc_row = self._chat_repo.get_tool_call(tc_db_id)
                    err_msg = str(exc)
                    duration_ms: int | None = None
                    if tc_row and tc_row.timestamp:
                        try:
                            ts = datetime.fromisoformat(
                                tc_row.timestamp.replace("Z", "+00:00")
                            )
                            duration_ms = int(
                                (datetime.now(timezone.utc) - ts).total_seconds()
                                * 1000
                            )
                        except (ValueError, TypeError):
                            pass
                    if tc_row and tc_row.status not in ("pending", "running"):
                        err_msg = tc_row.output_text or err_msg
                    elif tc_row:
                        self._chat_repo.set_tool_call_status(
                            tc_row,
                            status="error",
                            output_text=err_msg,
                            duration_ms=duration_ms,
                        )
                        self._chat_repo.commit()
                    tool_out = ToolCallOut(
                        id=tc_db_id,
                        name=tc_name,
                        status="error",
                        input=tc_input or {},
                        output=err_msg,
                        timestamp=utc_now_iso(),
                        duration=duration_ms,
                        isParallel=None,
                        parallelGroupId=None,
                    )
                    await self._event_bus.publish(
                        chat_id,
                        {
                            "type": "tool_call_end",
                            "payload": {"toolCall": tool_out.model_dump()},
                        },
                    )
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": err_msg,
                        }
                    )
            else:
                tc_ts = utc_now_iso()
                self._chat_repo.create_tool_call(
                    tool_call_id=tc_db_id,
                    chat_id=chat_id,
                    checkpoint_id=checkpoint_id,
                    name=tc_name,
                    status="pending",
                    input_json=tc_args_str,
                    timestamp=tc_ts,
                )
                self._chat_repo.commit()
                await self._event_bus.publish(
                    chat_id,
                    {
                        "type": "approval_required",
                        "payload": {
                            "toolCall": {
                                "id": tc_db_id,
                                "name": tc_name,
                                "status": "pending",
                                "input": tc_input,
                                "approvalRequired": True,
                                "checkpointId": checkpoint_id,
                                "timestamp": tc_ts,
                            }
                        },
                    },
                )
                result = await register_and_wait(chat_id, tc_db_id)
                tc_row = self._chat_repo.get_tool_call(tc_db_id)
                if (
                    result == "approved"
                    and tc_row
                    and tc_row.status == "completed"
                ):
                    output = tc_row.output_text or ""
                elif (
                    tc_row
                    and tc_row.status == "error"
                    and tc_row.output_text
                ):
                    output = tc_row.output_text
                else:
                    output = f"Rejected or timed out: {result}"
                    if (
                        tc_row
                        and tc_row.status == "rejected"
                        and tc_row.output_text
                    ):
                        output = tc_row.output_text
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": output,
                    }
                )
        return tool_results
