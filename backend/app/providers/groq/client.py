"""Groq API client for chat completions and model listing.

Uses the OpenAI-compatible API at https://api.groq.com/openai/v1.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, TypedDict

import httpx

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
RETRY_DELAYS = (5, 10, 15, 20)


def _should_retry(status_code: int) -> bool:
    """Retry on server errors (5xx) or rate limit (429)."""
    return status_code >= 500 or status_code == 429


class StreamContentEvent(TypedDict):
    type: str
    delta: str


class StreamToolCall(TypedDict, total=False):
    id: str
    type: str
    function: dict[str, Any]


class StreamToolCallsEvent(TypedDict):
    type: str
    tool_calls: list[StreamToolCall]


class StreamFinishEvent(TypedDict):
    type: str
    reason: str
    content: str


class StreamReasoningEvent(TypedDict):
    type: str
    reasoning_block_id: str
    delta: str
    checkpoint_id: str | None


StreamEvent = (
    StreamContentEvent | StreamToolCallsEvent | StreamFinishEvent | StreamReasoningEvent
)


def _accumulate_tool_calls(
    delta: dict, accumulated: dict[int, dict[str, Any]]
) -> None:
    """Mutate accumulated with tool call deltas from delta."""
    tc_deltas = delta.get("tool_calls")
    if not isinstance(tc_deltas, list):
        return
    for tc in tc_deltas:
        if not isinstance(tc, dict):
            continue
        idx = tc.get("index")
        if idx is None:
            continue
        if idx not in accumulated:
            accumulated[idx] = {
                "id": "",
                "type": "function",
                "function": {"name": "", "arguments": ""},
            }
        acc = accumulated[idx]
        if tc.get("id"):
            acc["id"] = str(tc["id"])
        fn = tc.get("function")
        if isinstance(fn, dict):
            if fn.get("name"):
                acc["function"]["name"] = str(fn["name"])
            if fn.get("arguments"):
                acc["function"]["arguments"] += str(fn["arguments"])


def _build_tool_calls_list(
    accumulated: dict[int, dict[str, Any]]
) -> list[StreamToolCall]:
    """Build sorted tool_calls list from accumulated."""
    return [
        {
            "id": acc.get("id") or f"call_{i}",
            "type": "function",
            "function": {
                "name": acc["function"].get("name") or "unknown",
                "arguments": acc["function"].get("arguments") or "{}",
            },
        }
        for i in sorted(accumulated.keys())
        for acc in [accumulated[i]]
    ]


def _parse_sse_line(line: str) -> tuple[dict | None, bool]:
    """Parse SSE data line. Returns (parsed dict or None, stream_done)."""
    if not line.startswith("data: "):
        return (None, False)
    data = line[6:].strip()
    if not data:
        return (None, False)
    if data == "[DONE]":
        return (None, True)
    try:
        return (json.loads(data), False)
    except json.JSONDecodeError:
        return (None, False)


def _process_parsed_choice(
    parsed: dict,
    content_parts: list[str],
    accumulated: dict[int, dict[str, Any]],
) -> tuple[list[StreamEvent], str | None]:
    """
    Process parsed SSE choice. Returns (list of events to yield, finish_reason or None).
    """
    events: list[StreamEvent] = []
    choices = parsed.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return (events, None)
    first = choices[0] if isinstance(choices[0], dict) else {}
    delta = first.get("delta", {}) if isinstance(first, dict) else {}
    finish_reason = first.get("finish_reason")

    if isinstance(delta, dict):
        if delta.get("content"):
            content_parts.append(str(delta["content"]))
            events.append(StreamContentEvent(type="content", delta=str(delta["content"])))
        _accumulate_tool_calls(delta, accumulated)

    return (events, finish_reason)


async def _stream_chunk_events(
    response: httpx.Response,
    content_parts: list[str],
    accumulated: dict[int, dict[str, Any]],
):
    """Async generator: process SSE stream and yield events."""
    buffer = ""
    stream_done = False
    async for chunk in response.aiter_bytes(chunk_size=1024):
        if stream_done:
            break
        buffer += chunk.decode("utf-8", errors="replace")
        while "\n" in buffer or "\r" in buffer:
            line, _, buffer = buffer.partition("\n")
            parsed, stream_done = _parse_sse_line(line.rstrip("\r"))
            if parsed is None:
                if stream_done:
                    break
                continue
            delta_events, finish_reason = _process_parsed_choice(
                parsed, content_parts, accumulated
            )
            for ev in delta_events:
                yield ev
            if finish_reason:
                content_str = "".join(content_parts)
                tool_calls_list = _build_tool_calls_list(accumulated)
                if tool_calls_list:
                    yield StreamToolCallsEvent(
                        type="tool_calls", tool_calls=tool_calls_list
                    )
                yield StreamFinishEvent(
                    type="finish", reason=str(finish_reason), content=content_str
                )
                return
    content_str = "".join(content_parts)
    yield StreamFinishEvent(type="finish", reason="stop", content=content_str)


class GroqClient:
    """Groq API client for model catalog and chat completion calls."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """
        Initialize Groq client.

        Args:
            api_key: Optional API key. If not provided, uses env var GROQ_API_KEY.
            base_url: Optional base URL. Defaults to https://api.groq.com/openai/v1.
        """
        import os

        self._api_key = api_key or os.environ.get("GROQ_API_KEY") or ""
        self._base_url = (base_url or GROQ_BASE_URL).rstrip("/")

    def count_tokens(self, text: str, model: str) -> int | None:
        """Groq has no tokenize endpoint; returns None for tiktoken fallback."""
        return None

    async def get_models(self) -> list[dict]:
        """Fetch all available models from Groq API."""
        if not self._api_key:
            return []
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self._base_url}/models", headers=headers)
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", [])
            return data if isinstance(data, list) else []

    async def create_chat_completion(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int = 128,
        temperature: float = 0.0,
        tools: list[dict] | None = None,
    ) -> str:
        """Create a non-streaming chat completion."""
        if not self._api_key:
            return ""

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    body = response.json()
            except httpx.HTTPStatusError as e:
                if _should_retry(e.response.status_code) and attempt < len(RETRY_DELAYS):
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(
                        "Groq API %s, retrying in %ss (attempt %d/%d)",
                        e.response.status_code,
                        delay,
                        attempt + 2,
                        len(RETRY_DELAYS) + 1,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
            break

        choices = body.get("choices", []) if isinstance(body, dict) else []
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message", {}) if isinstance(first, dict) else {}
        content = message.get("content", "") if isinstance(message, dict) else ""
        return str(content) if content is not None else ""

    async def create_chat_completion_stream(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int = 128,
        temperature: float = 0.0,
        tools: list[dict] | None = None,
        reasoning: dict[str, Any] | None = None,
    ):
        """
        Stream chat completion from Groq.

        Yields structured events: content deltas, accumulated tool calls,
        and finish with reason (stop or tool_calls).
        Groq supports reasoning_effort for compatible models.
        """
        if not self._api_key:
            return

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        if reasoning and isinstance(reasoning, dict):
            effort = reasoning.get("effort")
            if effort:
                payload["reasoning_effort"] = effort

        accumulated: dict[int, dict[str, Any]] = {}
        content_parts: list[str] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(len(RETRY_DELAYS) + 1):
                try:
                    async with client.stream(
                        "POST",
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    ) as response:
                        if response.status_code >= 400:
                            err_body = await response.aread()
                            try:
                                err_json = json.loads(err_body.decode("utf-8"))
                                logger.error("Groq API error %s: %s", response.status_code, err_json)
                            except Exception:
                                logger.error("Groq API error %s: %s", response.status_code, err_body[:500])
                        response.raise_for_status()
                        async for ev in _stream_chunk_events(
                            response, content_parts, accumulated
                        ):
                            yield ev
                        return
                except httpx.HTTPStatusError as e:
                    if _should_retry(e.response.status_code) and attempt < len(RETRY_DELAYS):
                        delay = RETRY_DELAYS[attempt]
                        logger.warning(
                            "Groq API %s, retrying in %ss (attempt %d/%d)",
                            e.response.status_code,
                            delay,
                            attempt + 2,
                            len(RETRY_DELAYS) + 1,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise
