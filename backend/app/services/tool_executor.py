"""Encapsulates tool call handling (auto-approve vs manual-approve flow)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.schemas.chat import ToolCallOut
from app.services.approval_service import ApprovalService
from app.services.approval_waiter import get_approval_waiter
from app.utils.ids import generate_id
from app.utils.json_helpers import safe_parse_json
from app.utils.time import utc_now_iso


class ToolExecutor:
    """Handles tool call execution with approval flow."""

    def __init__(self, chat_repo, approval_svc, event_bus, *, session_factory=None):
        self._chat_repo = chat_repo
        self._approval_svc = approval_svc
        self._event_bus = event_bus
        self._session_factory = session_factory

    async def execute_tool_calls(
        self,
        *,
        tool_calls_from_stream: list[dict],
        chat_id: str,
        checkpoint_id: str,
    ) -> list[dict]:
        """Execute tool calls; return tool result messages for conversation."""
        is_parallel = len(tool_calls_from_stream) > 1
        parallel_group = generate_id("pg") if is_parallel else None

        if is_parallel:
            for tc in tool_calls_from_stream:
                self._create_tool_call_row(
                    tc, chat_id, checkpoint_id, parallel_group
                )
            self._chat_repo.commit()

            tasks = [
                self._execute_one(
                    tc, chat_id, checkpoint_id, parallel_group, is_parallel
                )
                for tc in tool_calls_from_stream
            ]
            raw = [r for r in await asyncio.gather(*tasks) if r is not None]
            return self._flatten_results(raw)

        results = []
        for tc in tool_calls_from_stream:
            r = await self._execute_one(
                tc, chat_id, checkpoint_id, None, False
            )
            if r:
                results.append(r)
        return self._flatten_results(results)

    def _flatten_results(
        self, raw: list[dict | list[dict]]
    ) -> list[dict]:
        """Flatten tool results; each item may be one message or [tool_msg, user_msg]."""
        out: list[dict] = []
        for r in raw:
            if isinstance(r, list):
                out.extend(r)
            else:
                out.append(r)
        return out

    def _tool_result_messages(self, tc_id: str, output: str) -> dict:
        """Build tool result message for continuation context."""
        return {"role": "tool", "tool_call_id": tc_id, "content": output}

    def _create_tool_call_row(
        self,
        tc: dict,
        chat_id: str,
        checkpoint_id: str,
        parallel_group: str | None,
    ) -> None:
        """Create a tool call DB row."""
        tc_id = tc.get("id", "")
        fn = tc.get("function", {}) or {}
        tc_name = fn.get("name", "unknown")
        tc_args_str = fn.get("arguments", "{}")
        tc_db_id = tc_id if tc_id.startswith("tc-") else f"tc-{tc_id}"
        self._chat_repo.create_tool_call(
            tool_call_id=tc_db_id,
            chat_id=chat_id,
            checkpoint_id=checkpoint_id,
            name=tc_name,
            status="pending",
            input_json=tc_args_str,
            timestamp=utc_now_iso(),
            parallel_group=parallel_group,
        )

    async def _execute_one(
        self,
        tc: dict,
        chat_id: str,
        checkpoint_id: str,
        parallel_group: str | None,
        is_parallel: bool,
    ) -> dict | list[dict] | None:
        """Execute a single tool call. Returns one message dict or [tool_msg, user_msg] when spill."""
        tc_id = tc.get("id", "")
        fn = tc.get("function", {}) or {}
        tc_name = fn.get("name", "unknown")
        tc_args_str = fn.get("arguments", "{}")
        tc_input = safe_parse_json(tc_args_str)
        tc_db_id = tc_id if tc_id.startswith("tc-") else f"tc-{tc_id}"
        auto_approved = self._approval_svc.should_auto_approve(
            tc_name, tc_input or {}
        )

        if not is_parallel:
            self._create_tool_call_row(tc, chat_id, checkpoint_id, parallel_group)
            self._chat_repo.commit()

        if auto_approved:
            if is_parallel and self._session_factory:
                return await self._run_approve_isolated(
                    chat_id=chat_id,
                    tc_id=tc_id,
                    tc_db_id=tc_db_id,
                    tc_name=tc_name,
                    tc_input=tc_input,
                    parallel_group=parallel_group or "",
                )
            return await self._run_approve_inline(
                chat_id=chat_id,
                tc_id=tc_id,
                tc_db_id=tc_db_id,
                tc_name=tc_name,
                tc_input=tc_input,
            )
        return await self._run_wait_manual(
            chat_id=chat_id,
            checkpoint_id=checkpoint_id,
            tc_id=tc_id,
            tc_db_id=tc_db_id,
            tc_name=tc_name,
            tc_input=tc_input,
            parallel_group=parallel_group,
        )

    async def _run_approve_isolated(
        self,
        *,
        chat_id: str,
        tc_id: str,
        tc_db_id: str,
        tc_name: str,
        tc_input: dict | None,
        parallel_group: str,
    ) -> dict | list[dict] | None:
        """Run approve() in an isolated session for parallel execution."""
        sf = self._session_factory
        if sf is None:
            raise RuntimeError("session_factory required for parallel tool execution")
        with sf() as session:
            approval_svc = ApprovalService(session, event_bus=self._event_bus)
            try:
                tool_out, _ = await approval_svc.approve(
                    chat_id=chat_id, tool_call_id=tc_db_id
                )
                return self._tool_result_messages(tc_id, tool_out.output or "")
            except Exception as exc:
                return await self._handle_approve_error(
                    exc, tc_db_id, tc_name, tc_input, tc_id, chat_id, parallel_group
                )

    async def _run_approve_inline(
        self,
        *,
        chat_id: str,
        tc_id: str,
        tc_db_id: str,
        tc_name: str,
        tc_input: dict | None,
    ) -> dict | list[dict] | None:
        """Run approve() using the shared approval service (sequential)."""
        try:
            tool_out, _ = await self._approval_svc.approve(
                chat_id=chat_id, tool_call_id=tc_db_id
            )
            return self._tool_result_messages(tc_id, tool_out.output or "")
        except Exception as exc:
            return await self._handle_approve_error(
                exc, tc_db_id, tc_name, tc_input, tc_id, chat_id, None
            )

    async def _handle_approve_error(
        self,
        exc: Exception,
        tc_db_id: str,
        tc_name: str,
        tc_input: dict | None,
        tc_id: str,
        chat_id: str,
        parallel_group: str | None = None,
    ) -> dict | list[dict] | None:
        """Handle exception from approve(); update DB and publish."""
        tc_row = self._chat_repo.get_tool_call(tc_db_id)
        err_msg = str(exc)
        duration_ms: int | None = None
        if tc_row and tc_row.timestamp:
            try:
                ts = datetime.fromisoformat(tc_row.timestamp.replace("Z", "+00:00"))
                duration_ms = int(
                    (datetime.now(timezone.utc) - ts).total_seconds() * 1000
                )
            except (ValueError, TypeError):
                pass
        if tc_row and tc_row.status not in ("pending", "running"):
            err_msg = tc_row.output_text or err_msg
        elif tc_row:
            self._chat_repo.set_tool_call_status(
                tc_row, status="error", output_text=err_msg, duration_ms=duration_ms
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
            isParallel=bool(parallel_group) if parallel_group else None,
            parallelGroupId=parallel_group,
            artifacts=[],
        )
        await self._event_bus.publish(
            chat_id,
            {"type": "tool_call_end", "payload": {"toolCall": tool_out.model_dump()}},
        )
        return {"role": "tool", "tool_call_id": tc_id, "content": err_msg}

    async def _run_wait_manual(
        self,
        *,
        chat_id: str,
        checkpoint_id: str,
        tc_id: str,
        tc_db_id: str,
        tc_name: str,
        tc_input: dict | None,
        parallel_group: str | None,
    ) -> dict | list[dict] | None:
        """Wait for manual approval (execution happens in approve endpoint)."""
        tc_ts = utc_now_iso()
        payload = {
            "toolCall": {
                "id": tc_db_id,
                "name": tc_name,
                "status": "pending",
                "input": tc_input,
                "approvalRequired": True,
                "checkpointId": checkpoint_id,
                "timestamp": tc_ts,
            }
        }
        if parallel_group:
            payload["toolCall"]["isParallel"] = True
            payload["toolCall"]["parallelGroupId"] = parallel_group
        await self._event_bus.publish(
            chat_id, {"type": "approval_required", "payload": payload}
        )
        result = await get_approval_waiter().register_and_wait(chat_id, tc_db_id)
        # The approve endpoint runs in a separate DB session, so the
        # identity-map cached object is stale.  Expire it first so
        # get_tool_call hits the database for fresh data.
        cached = self._chat_repo.get_tool_call(tc_db_id)
        if cached is not None:
            self._chat_repo.db.refresh(cached)
        tc_row = cached
        if result == "approved" and tc_row and tc_row.status == "completed":
            output = tc_row.output_text or ""
        elif tc_row and tc_row.status == "error" and tc_row.output_text:
            output = tc_row.output_text
        else:
            output = f"Rejected or timed out: {result}"
            if tc_row and tc_row.status == "rejected" and tc_row.output_text:
                output = tc_row.output_text
        return self._tool_result_messages(tc_id, output)
