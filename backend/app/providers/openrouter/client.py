from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, TypedDict

import httpx

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


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

RETRY_DELAYS = (5, 10, 15, 20)


def _should_retry(status_code: int) -> bool:
    """Retry on server errors (5xx) or rate limit (429)."""
    return status_code >= 500 or status_code == 429


def _log_stream_error(response, body_bytes: bytes) -> None:
    """Log OpenRouter stream error and parse error body."""
    try:
        err_body = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        err_body = body_bytes.decode("utf-8", errors="replace")
    logger.error("OpenRouter API error %s: %s", response.status_code, err_body)


def _yield_reasoning_from_content(
    delta: dict, reasoning_accumulated: dict[int, dict[str, Any]]
) -> StreamEvent | None:
    """Handle reasoning_content or reasoning field; returns event or None."""
    rd_content = delta.get("reasoning_content") or delta.get("reasoning")
    if not isinstance(rd_content, str) or not rd_content:
        return None
    logger.info(
        "OpenRouter stream: reasoning_content/reasoning chunk (%d chars)",
        len(rd_content),
    )
    bid = "rb-0"
    if 0 not in reasoning_accumulated:
        reasoning_accumulated[0] = {"id": bid, "content": ""}
    reasoning_accumulated[0]["content"] += rd_content
    return {
        "type": "reasoning",
        "reasoning_block_id": bid,
        "delta": rd_content,
        "checkpoint_id": None,
    }


def _reasoning_events_from_details(
    delta: dict, reasoning_accumulated: dict[int, dict[str, Any]]
) -> list[StreamEvent]:
    """Handle reasoning_details list; returns reasoning events."""
    result: list[StreamEvent] = []
    rd_deltas = delta.get("reasoning_details")
    if not isinstance(rd_deltas, list):
        return result
    logger.info(
        "OpenRouter stream: reasoning_details chunk, %d items", len(rd_deltas)
    )
    for rd in rd_deltas:
        if not isinstance(rd, dict):
            continue
        idx = rd.get("index", 0)
        rd_type = rd.get("type", "")
        text = rd.get("text") or rd.get("summary") or ""
        if rd.get("type") == "reasoning.encrypted":
            text = "[REDACTED]"
        if not text and rd_type not in ("reasoning.encrypted",):
            continue
        bid = rd.get("id") or f"rb-{idx}"
        if idx not in reasoning_accumulated:
            reasoning_accumulated[idx] = {"id": bid, "content": ""}
        reasoning_accumulated[idx]["content"] += str(text)
        result.append({
            "type": "reasoning",
            "reasoning_block_id": bid,
            "delta": str(text),
            "checkpoint_id": None,
        })
    return result


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


async def _stream_chunk_events(
    response: httpx.Response,
    content_parts: list[str],
    accumulated: dict[int, dict[str, Any]],
    reasoning_accumulated: dict[int, dict[str, Any]],
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
                parsed, content_parts, accumulated, reasoning_accumulated
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
    reasoning_accumulated: dict[int, dict[str, Any]],
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
        reasoning_keys = [k for k in ("reasoning", "reasoning_content", "reasoning_details") if k in delta]
        if reasoning_keys:
            logger.info("OpenRouter stream: delta has reasoning keys=%s", reasoning_keys)
        if delta.get("content"):
            content_parts.append(str(delta["content"]))
            events.append(StreamContentEvent(type="content", delta=str(delta["content"])))
        ev = _yield_reasoning_from_content(delta, reasoning_accumulated)
        if ev is not None:
            events.append(ev)
        else:
            events.extend(_reasoning_events_from_details(delta, reasoning_accumulated))
        _accumulate_tool_calls(delta, accumulated)

    return (events, finish_reason)


class OpenRouterClient:
    """OpenRouter API client for model catalog and chat completion calls."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        """
        Initialize OpenRouter client.

        Args:
            api_key: Optional API key. If not provided, uses env var OPENROUTER_API_KEY
            base_url: Optional base URL. If not provided, uses default or env var
        """
        settings = get_settings()

        # Use provided values or fall back to env vars/defaults
        self._api_key = api_key or settings.openrouter_api_key
        self._base_url = (base_url or settings.openrouter_base_url).rstrip("/")

    def count_tokens(self, text: str, model: str) -> int | None:
        """OpenRouter has no tokenize endpoint; returns None for tiktoken fallback."""
        return None

    async def get_models(self) -> list[dict]:
        if not self._api_key:
            return []
        headers = {"Authorization": f"Bearer {self._api_key}"}
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
        if not self._api_key:
            return ""

        headers = {"Authorization": f"Bearer {self._api_key}"}
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
                        "OpenRouter API %s, retrying in %ss (attempt %d/%d)",
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
        Stream chat completion from OpenRouter.

        Yields structured events: content deltas, reasoning deltas,
        accumulated tool calls, and finish with reason (stop or tool_calls).
        """
        if not self._api_key:
            return

        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        if reasoning:
            payload["reasoning"] = reasoning
            logger.info(
                "OpenRouter stream: requesting reasoning with config %s", reasoning
            )

        accumulated: dict[int, dict[str, Any]] = {}
        content_parts: list[str] = []
        reasoning_accumulated: dict[int, dict[str, Any]] = {}

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
                            _log_stream_error(response, await response.aread())
                        response.raise_for_status()
                        async for ev in _stream_chunk_events(
                            response, content_parts, accumulated, reasoning_accumulated
                        ):
                            yield ev
                        return
                except httpx.HTTPStatusError as e:
                    if _should_retry(e.response.status_code) and attempt < len(
                        RETRY_DELAYS
                    ):
                        delay = RETRY_DELAYS[attempt]
                        logger.warning(
                            "OpenRouter API %s, retrying in %ss (attempt %d/%d)",
                            e.response.status_code,
                            delay,
                            attempt + 2,
                            len(RETRY_DELAYS) + 1,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise
