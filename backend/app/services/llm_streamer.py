"""Encapsulates one LLM streaming call and SSE event publishing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.utils.ids import generate_id
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)


@dataclass
class StreamResult:
    """Result of a single streaming LLM call."""

    text: str
    tool_calls: list[dict]
    reasoning_blocks: dict[str, str]
    finish_reason: str
    finish_content: str


class LLMStreamer:
    """Handles one LLM streaming call and publishes content/reasoning/tool_calls events."""

    def __init__(self, chat_repo, event_bus):
        self._chat_repo = chat_repo
        self._event_bus = event_bus

    async def _emit_reasoning_end(
        self,
        chat_id: str,
        checkpoint_id: str | None,
        rb_id: str,
        reasoning_block_ts: str,
        reasoning_content: list[str],
    ) -> None:
        """Emit reasoning_end and persist block when reasoning finishes."""
        content = "".join(reasoning_content)
        if not content:
            return
        reasoning_content.clear()
        duration_ms = None
        try:
            start_dt = datetime.fromisoformat(
                reasoning_block_ts.replace("Z", "+00:00")
            )
            duration_ms = int(
                (datetime.now(timezone.utc) - start_dt).total_seconds() * 1000
            )
        except (ValueError, TypeError):
            pass
        self._chat_repo.create_reasoning_block(
            reasoning_block_id=rb_id,
            chat_id=chat_id,
            checkpoint_id=checkpoint_id,
            content=content,
            timestamp=reasoning_block_ts,
            duration_ms=duration_ms,
        )
        # Commit before publishing so the block is queryable when the frontend
        # calls getChatHistory in response to this event.
        self._chat_repo.commit()
        try:
            import tiktoken
            _enc = tiktoken.get_encoding("cl100k_base")
            tokens = len(_enc.encode(content))
        except Exception:
            tokens = max(1, len(content) // 4)
        block_out = {
            "id": rb_id,
            "content": content,
            "timestamp": reasoning_block_ts,
            "checkpointId": checkpoint_id,
            "duration": duration_ms,
            "tokens": tokens,
        }
        await self._event_bus.publish(
            chat_id,
            {"type": "reasoning_end", "payload": {"reasoningBlock": block_out}},
        )
        logger.info(
            "Emitted reasoning block %s for chat_id=%s checkpoint_id=%s",
            rb_id,
            chat_id,
            checkpoint_id,
        )

    async def stream_completion(
        self,
        *,
        client,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
        reasoning_param: dict | None,
        chat_id: str,
        msg_id: str,
        ts: str,
        checkpoint_id: str | None,
        reasoning_block_id: str | None = None,
        silent: bool = False,
        suppress_content_events: bool = False,
    ) -> StreamResult:
        response_chunks: list[str] = []
        tool_calls_from_stream: list[dict] = []
        finish_reason = "stop"
        finish_content = ""
        rb_id = reasoning_block_id or generate_id("rb")
        reasoning_content: list[str] = []
        reasoning_started = False
        reasoning_block_ts = ts

        def _should_publish() -> bool:
            return not silent

        def _should_publish_content() -> bool:
            return not silent and not suppress_content_events

        async for ev in client.create_chat_completion_stream(
            model=model,
            messages=messages,
            max_tokens=4096,
            temperature=0.7,
            tools=tools if tools else None,
            reasoning=reasoning_param,
        ):
            if ev.get("type") == "content":
                if reasoning_started and reasoning_content and _should_publish():
                    await self._emit_reasoning_end(
                        chat_id, checkpoint_id, rb_id, reasoning_block_ts, reasoning_content
                    )
                    reasoning_started = False
                delta = ev.get("delta", "")
                response_chunks.append(delta)
                if _should_publish_content():
                    await self._event_bus.publish(
                        chat_id,
                        {
                            "type": "content_delta",
                            "payload": {"messageId": msg_id, "delta": delta},
                        },
                    )
            elif ev.get("type") == "reasoning":
                delta_text = ev.get("delta", "")
                if delta_text:
                    is_first = not reasoning_started
                    if is_first:
                        rb_id = generate_id("rb")
                        reasoning_block_ts = utc_now_iso()
                    reasoning_started = True
                    reasoning_content.append(delta_text)
                    if _should_publish():
                        if is_first:
                            block_out = {
                                "id": rb_id,
                                "content": "".join(reasoning_content),
                                "timestamp": reasoning_block_ts,
                                "checkpointId": checkpoint_id,
                            }
                            await self._event_bus.publish(
                                chat_id,
                                {
                                    "type": "reasoning_start",
                                    "payload": {"reasoningBlock": block_out},
                                },
                            )
                        else:
                            await self._event_bus.publish(
                                chat_id,
                                {
                                    "type": "reasoning_delta",
                                    "payload": {
                                        "reasoningBlockId": rb_id,
                                        "delta": delta_text,
                                    },
                                },
                            )
            elif ev.get("type") == "tool_calls":
                if reasoning_started and reasoning_content and _should_publish():
                    await self._emit_reasoning_end(
                        chat_id, checkpoint_id, rb_id, reasoning_block_ts, reasoning_content
                    )
                    reasoning_started = False
                tool_calls_from_stream = ev.get("tool_calls", [])
            elif ev.get("type") == "finish":
                finish_reason = ev.get("reason", "stop")
                finish_content = ev.get("content", "")
                if reasoning_started and reasoning_content and _should_publish():
                    await self._emit_reasoning_end(
                        chat_id, checkpoint_id, rb_id, reasoning_block_ts, reasoning_content
                    )

        response_text = (
            "".join(response_chunks).strip() if response_chunks else ""
        )
        content = "".join(reasoning_content)
        reasoning_blocks = {rb_id: content} if content else {}
        return StreamResult(
            text=response_text,
            tool_calls=tool_calls_from_stream,
            reasoning_blocks=reasoning_blocks,
            finish_reason=finish_reason,
            finish_content=finish_content,
        )
