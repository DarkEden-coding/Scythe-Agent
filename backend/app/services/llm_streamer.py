"""Encapsulates one LLM streaming call and SSE event publishing."""

from __future__ import annotations

import logging
from dataclasses import dataclass

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

    async def stream_completion(
        self,
        *,
        client,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
        reasoning_param: dict,
        chat_id: str,
        msg_id: str,
        ts: str,
        checkpoint_id: str,
    ) -> StreamResult:
        response_chunks: list[str] = []
        tool_calls_from_stream: list[dict] = []
        finish_reason = "stop"
        finish_content = ""
        reasoning_blocks_accumulated: dict[str, str] = {}

        async for ev in client.create_chat_completion_stream(
            model=model,
            messages=messages,
            max_tokens=4096,
            temperature=0.7,
            tools=tools if tools else None,
            reasoning=reasoning_param,
        ):
            if ev.get("type") == "content":
                delta = ev.get("delta", "")
                response_chunks.append(delta)
                await self._event_bus.publish(
                    chat_id,
                    {
                        "type": "content_delta",
                        "payload": {"messageId": msg_id, "delta": delta},
                    },
                )
            elif ev.get("type") == "reasoning":
                rb_id = ev.get("reasoning_block_id", "")
                delta_text = ev.get("delta", "")
                if rb_id and delta_text:
                    is_first = rb_id not in reasoning_blocks_accumulated
                    if is_first:
                        reasoning_blocks_accumulated[rb_id] = ""
                    reasoning_blocks_accumulated[rb_id] += delta_text
                    if is_first:
                        block_out = {
                            "id": rb_id,
                            "content": reasoning_blocks_accumulated[rb_id],
                            "timestamp": ts,
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
                tool_calls_from_stream = ev.get("tool_calls", [])
            elif ev.get("type") == "finish":
                finish_reason = ev.get("reason", "stop")
                finish_content = ev.get("content", "")
                for rb_id, content in reasoning_blocks_accumulated.items():
                    if not content:
                        continue
                    db_rb_id = generate_id("rb")
                    self._chat_repo.create_reasoning_block(
                        reasoning_block_id=db_rb_id,
                        chat_id=chat_id,
                        checkpoint_id=checkpoint_id,
                        content=content,
                        timestamp=ts,
                        duration_ms=None,
                    )
                    block_out = {
                        "id": rb_id,
                        "content": content,
                        "timestamp": ts,
                        "checkpointId": checkpoint_id,
                    }
                    await self._event_bus.publish(
                        chat_id,
                        {"type": "reasoning_end", "payload": {"reasoningBlock": block_out}},
                    )
                if reasoning_blocks_accumulated:
                    self._chat_repo.commit()
                    logger.info(
                        "Emitted %d reasoning blocks for chat_id=%s checkpoint_id=%s",
                        len(reasoning_blocks_accumulated),
                        chat_id,
                        checkpoint_id,
                    )

        response_text = (
            "".join(response_chunks).strip() if response_chunks else ""
        )
        return StreamResult(
            text=response_text,
            tool_calls=tool_calls_from_stream,
            reasoning_blocks=reasoning_blocks_accumulated,
            finish_reason=finish_reason,
            finish_content=finish_content,
        )
