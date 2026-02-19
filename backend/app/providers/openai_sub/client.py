"""OpenAI Subscription client using OAuth token and Codex Responses API.

Uses ChatGPT Plus/Pro/Team/Enterprise subscription caps via OAuth 2.1 + PKCE.
Per roo-code: requests route to chatgpt.com/backend-api/codex (not api.openai.com).
"""

from __future__ import annotations

import json
import logging
import platform
import uuid
from typing import Any, TypedDict, cast

import httpx

logger = logging.getLogger(__name__)

CODEX_API_BASE = "https://chatgpt.com/backend-api/codex"

_OPENAI_SUB_MODEL_IDS = [
    "gpt-5",
    "gpt-5-codex",
    "gpt-5-codex-mini",
    "gpt-5.1",
    "gpt-5.1-codex",
    "gpt-5.1-codex-max",
    "gpt-5.1-codex-mini",
    "gpt-5.2",
    "gpt-5.2-codex",
    "gpt-5.3-codex",
]


class StreamContentEvent(TypedDict):
    type: str
    delta: str


class StreamReasoningEvent(TypedDict):
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


StreamEvent = (
    StreamContentEvent | StreamReasoningEvent | StreamToolCallsEvent | StreamFinishEvent
)


def _sanitize_call_id(call_id: str, max_len: int = 64) -> str:
    """Truncate call_id to fit OpenAI limit."""
    if len(call_id) <= max_len:
        return call_id
    return call_id[:max_len]


def _ensure_additional_properties_false(schema: dict) -> dict:
    """Recursively set additionalProperties: false on object schemas."""
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return schema
    result = {**schema, "additionalProperties": False}
    if "properties" in result:
        new_props = {}
        for key, prop in result["properties"].items():
            if isinstance(prop, dict):
                if prop.get("type") == "object":
                    new_props[key] = _ensure_additional_properties_false(prop)
                elif prop.get("type") == "array" and isinstance(prop.get("items"), dict) and prop["items"].get("type") == "object":
                    new_props[key] = {**prop, "items": _ensure_additional_properties_false(prop["items"])}
                else:
                    new_props[key] = prop
            else:
                new_props[key] = prop
        result["properties"] = new_props
    return result


def _ensure_all_required(schema: dict) -> dict:
    """Recursively make all properties required and set additionalProperties: false."""
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return schema
    result = {**schema, "additionalProperties": False}
    if "properties" in result:
        result["required"] = list(result["properties"].keys())
        new_props = {}
        for key, prop in result["properties"].items():
            if isinstance(prop, dict):
                if prop.get("type") == "object":
                    new_props[key] = _ensure_all_required(prop)
                elif prop.get("type") == "array" and isinstance(prop.get("items"), dict) and prop["items"].get("type") == "object":
                    new_props[key] = {**prop, "items": _ensure_all_required(prop["items"])}
                else:
                    new_props[key] = prop
            else:
                new_props[key] = prop
        result["properties"] = new_props
    return result


def _messages_to_codex_input(messages: list[dict]) -> tuple[list[dict], str]:
    """Convert OpenRouter-style messages to Codex input format.

    Returns (input, instructions).
    Per the Responses API, function_call items are top-level in the input array,
    not nested inside assistant message content.
    """
    input_items: list[dict] = []
    instructions = ""

    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")

        if role == "system":
            instructions = (instructions + "\n\n" + content).strip() if instructions else str(content)
            continue

        if role == "user":
            text = content if isinstance(content, str) else ""
            if text:
                input_items.append({
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                })
            continue

        if role == "assistant":
            # Text content goes in { role: "assistant", content: [...] }
            text_content: list[dict] = []
            if content:
                text_content.append({"type": "output_text", "text": str(content)})
            if text_content:
                input_items.append({"role": "assistant", "content": text_content})

            # Tool calls are SEPARATE top-level items (not nested in assistant content)
            tool_calls = m.get("tool_calls") or []
            for tc in tool_calls:
                fn = tc.get("function", {}) or {}
                input_items.append({
                    "type": "function_call",
                    "call_id": _sanitize_call_id(tc.get("id", "") or f"call_{uuid.uuid4().hex[:8]}"),
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", "{}"),
                })
            continue

        if role == "tool":
            tool_call_id = m.get("tool_call_id", "")
            output = content if isinstance(content, str) else str(content or "")
            input_items.append({
                "type": "function_call_output",
                "call_id": _sanitize_call_id(tool_call_id),
                "output": output,
            })

    return (input_items, instructions or "You are a helpful assistant.")


def _openrouter_tools_to_responses(tools: list[dict]) -> list[dict]:
    """Convert OpenRouter/OpenAI function format to Responses API tools with strict schemas."""
    result = []
    for t in tools or []:
        if t.get("type") == "function" and "function" in t:
            fn = t["function"]
            params = fn.get("parameters", {"type": "object"})
            result.append(
                {
                    "type": "function",
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "parameters": _ensure_all_required(params),
                    "strict": True,
                }
            )
    return result


def _parse_sse_line(line: str) -> tuple[dict | None, bool]:
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


def _extract_from_responses_output(output: list[dict]) -> tuple[str, list[dict], str]:
    """Extract text, tool_calls, finish_reason from Codex/Responses API output."""
    text_parts: list[str] = []
    tool_calls: list[dict] = []
    finish_reason = "stop"
    for item in output or []:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind == "message":
            content = item.get("content", [])
            for c in content if isinstance(content, list) else []:
                if isinstance(c, dict) and c.get("type") == "output_text":
                    text_parts.append(c.get("text", ""))
        elif kind in ("function_call", "tool_call"):
            call_id = item.get("call_id") or item.get("id", "")
            name = item.get("name", "")
            args_str = item.get("arguments", "{}")
            tool_calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": args_str},
                }
            )
            finish_reason = "tool_calls"
    return ("".join(text_parts), tool_calls, finish_reason)


def _find_accumulated_idx_by_call_id(accumulated: dict, call_id: str) -> int | None:
    """Find existing accumulated tool call entry by call_id to prevent duplicates."""
    if not call_id:
        return None
    for idx, acc in accumulated.items():
        if acc.get("id") == call_id:
            return idx
    return None


def _process_stream_event(
    parsed: dict, content_parts: list[str], accumulated: dict,
    reasoning_parts: list[str] | None = None,
) -> tuple[list[StreamEvent], str | None]:
    """Process SSE event from Codex or Responses API. Returns (events, finish_reason)."""
    events: list[StreamEvent] = []
    ev_type = parsed.get("type")

    # --- Error events ---
    if ev_type in ("response.error", "error"):
        msg = (parsed.get("error") or {}).get("message") or parsed.get("message") or "Unknown API error"
        raise RuntimeError(f"OpenAI Sub API error: {msg}")

    if ev_type == "response.failed":
        msg = (parsed.get("error") or {}).get("message") or parsed.get("message") or "Unknown failure"
        raise RuntimeError(f"OpenAI Sub API response failed: {msg}")

    # --- Text deltas ---
    if ev_type in ("response.text.delta", "response.output_text.delta"):
        delta = parsed.get("delta")
        if delta:
            content_parts.append(delta)
            events.append(StreamContentEvent(type="content", delta=str(delta)))
        return (events, None)

    # --- Reasoning deltas ---
    if ev_type in (
        "response.reasoning.delta",
        "response.reasoning_text.delta",
        "response.reasoning_summary.delta",
        "response.reasoning_summary_text.delta",
    ):
        delta = parsed.get("delta")
        if delta:
            if reasoning_parts is not None:
                reasoning_parts.append(str(delta))
            events.append(StreamReasoningEvent(type="reasoning", delta=str(delta)))
        return (events, None)

    # --- Refusal deltas ---
    if ev_type == "response.refusal.delta":
        delta = parsed.get("delta")
        if delta:
            content_parts.append(f"[Refusal] {delta}")
            events.append(StreamContentEvent(type="content", delta=f"[Refusal] {delta}"))
        return (events, None)

    # --- Tool/function call argument deltas ---
    if ev_type in ("response.tool_call_arguments.delta", "response.function_call_arguments.delta"):
        idx = parsed.get("index", 0)
        delta = parsed.get("delta") or parsed.get("arguments", "")
        if idx in accumulated and delta:
            accumulated[idx]["function"]["arguments"] += str(delta)
        return (events, None)

    # --- Output item added/done for function_call ---
    if ev_type in ("response.output_item.added", "response.output_item.done"):
        item = parsed.get("item")
        if isinstance(item, dict) and item.get("type") in ("function_call", "tool_call"):
            call_id = item.get("call_id") or item.get("tool_call_id") or item.get("id", "")
            name = item.get("name") or (item.get("function") or {}).get("name", "")
            args = item.get("arguments", "")
            # Look up existing entry by call_id first to prevent duplicates
            existing_idx = _find_accumulated_idx_by_call_id(accumulated, str(call_id))
            idx = existing_idx if existing_idx is not None else item.get("index", len(accumulated))
            if idx not in accumulated:
                accumulated[idx] = {
                    "id": str(call_id),
                    "type": "function",
                    "function": {"name": str(name), "arguments": str(args)},
                }
            else:
                acc = accumulated[idx]
                if call_id:
                    acc["id"] = str(call_id)
                if name:
                    acc["function"]["name"] = str(name)
                # Only append args on "added" (first time); "done" has complete args
                if ev_type == "response.output_item.done" and args:
                    acc["function"]["arguments"] = str(args)
                elif args:
                    acc["function"]["arguments"] += str(args)
        return (events, None)

    # --- Completion events: response.done, response.completed ---
    # Text and reasoning were already streamed via delta events. Only extract
    # from the final output if nothing was streamed (fallback for non-streaming paths).
    if ev_type in ("response.done", "response.completed"):
        resp = parsed.get("response") or {}
        output = resp.get("output") or []
        has_tool_calls = False
        content_already_streamed = len(content_parts) > 0
        reasoning_already_streamed = bool(reasoning_parts)
        for item in output if isinstance(output, list) else []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message" and not content_already_streamed:
                for c in item.get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "output_text":
                        text = c.get("text", "")
                        if text:
                            content_parts.append(text)
                            events.append(StreamContentEvent(type="content", delta=text))
            elif item.get("type") == "reasoning" and isinstance(item.get("summary"), list) and not reasoning_already_streamed:
                for summary in item["summary"]:
                    if isinstance(summary, dict) and summary.get("type") == "summary_text":
                        text = summary.get("text", "")
                        if text:
                            events.append(StreamReasoningEvent(type="reasoning", delta=text))
            elif item.get("type") in ("function_call", "tool_call"):
                has_tool_calls = True
                call_id = str(item.get("call_id") or item.get("id", ""))
                # Skip if already accumulated from streaming events
                existing_idx = _find_accumulated_idx_by_call_id(accumulated, call_id)
                if existing_idx is not None:
                    # Update with final data
                    acc = accumulated[existing_idx]
                    if item.get("name"):
                        acc["function"]["name"] = str(item["name"])
                    if item.get("arguments"):
                        acc["function"]["arguments"] = str(item["arguments"])
                else:
                    idx = item.get("index", len(accumulated))
                    accumulated[idx] = {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": str(item.get("name", "")),
                            "arguments": str(item.get("arguments", "{}")),
                        },
                    }
        finish = "tool_calls" if (has_tool_calls or accumulated) else ("stop" if output else None)
        return (events, finish)

    # --- Legacy api.openai.com format: output_delta ---
    output = parsed.get("output") or parsed.get("output_delta")
    if output:
        items = output if isinstance(output, list) else [output]
        for item in items:
            if not isinstance(item, dict):
                continue
            kind = item.get("type")
            if kind == "message":
                for c in item.get("content") or []:
                    if isinstance(c, dict):
                        delta_text = c.get("text") or c.get("delta", "")
                        if delta_text:
                            content_parts.append(delta_text)
                            events.append(StreamContentEvent(type="content", delta=str(delta_text)))
            elif kind == "function_call":
                idx = item.get("index", 0)
                if idx not in accumulated:
                    accumulated[idx] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                acc = accumulated[idx]
                if item.get("id"):
                    acc["id"] = str(item["id"])
                if item.get("name"):
                    acc["function"]["name"] = str(item["name"])
                if item.get("arguments"):
                    acc["function"]["arguments"] += str(item["arguments"])
    return (events, None)


def _codex_headers(
    access_token: str, session_id: str, *, account_id: str | None = None
) -> dict[str, str]:
    """Build Codex-specific headers required for subscription auth."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "originator": "scythe-agent",
        "session_id": session_id,
        "User-Agent": f"scythe-agent/1 (Python {platform.python_version()}; {platform.system()} {platform.release()})",
    }
    if account_id:
        headers["ChatGPT-Account-Id"] = account_id
    return headers


class OpenAISubClient:
    """Client for OpenAI Codex Responses API using subscription OAuth token."""

    def __init__(self, access_token: str, *, account_id: str | None = None) -> None:
        self._access_token = access_token
        self._session_id = str(uuid.uuid4())
        self._account_id = account_id

    def count_tokens(self, text: str, model: str) -> int | None:
        return None

    async def get_models(self) -> list[dict]:
        """Return subscription models. /v1/models returns 403 for OAuth tokens."""
        return [{"id": m} for m in _OPENAI_SUB_MODEL_IDS]

    async def create_chat_completion(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int = 128,
        temperature: float = 0.0,
        tools: list[dict] | None = None,
    ) -> str:
        input_items, instructions = _messages_to_codex_input(messages)
        resp_tools = _openrouter_tools_to_responses(tools) if tools else None
        payload: dict = {
            "model": model,
            "input": input_items,
            "instructions": instructions,
            "stream": False,
            "store": False,
        }
        if resp_tools:
            payload["tools"] = resp_tools
            payload["parallel_tool_calls"] = True
        headers = _codex_headers(self._access_token, self._session_id, account_id=self._account_id)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{CODEX_API_BASE}/responses",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        output = body.get("output") or (body.get("response") or {}).get("output") or []
        text, _, _ = _extract_from_responses_output(output)
        return text

    async def create_chat_completion_stream(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int = 128,
        temperature: float = 0.0,
        tools: list[dict] | None = None,
        reasoning: dict[str, Any] | None = None,
        tool_choice: Any = None,
    ):
        input_items, instructions = _messages_to_codex_input(messages)
        resp_tools = _openrouter_tools_to_responses(tools) if tools else None
        payload: dict = {
            "model": model,
            "input": input_items,
            "instructions": instructions,
            "stream": True,
            "store": False,
        }
        if resp_tools:
            payload["tools"] = resp_tools
            payload["parallel_tool_calls"] = True
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        # Reasoning configuration
        if reasoning:
            effort = reasoning.get("effort")
            if effort and effort not in ("disable", "none"):
                payload["reasoning"] = {"effort": effort, "summary": "auto"}
                payload["include"] = ["reasoning.encrypted_content"]

        headers = _codex_headers(self._access_token, self._session_id, account_id=self._account_id)
        accumulated: dict[int, dict[str, Any]] = {}
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{CODEX_API_BASE}/responses",
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    err_body = await response.aread()
                    try:
                        err_json = json.loads(err_body.decode("utf-8"))
                        logger.error(
                            "OpenAI Sub API error %s: %s",
                            response.status_code,
                            err_json,
                        )
                    except Exception:
                        logger.error("OpenAI Sub API error %s", response.status_code)
                response.raise_for_status()
                buffer = ""
                async for chunk in response.aiter_bytes(chunk_size=1024):
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer or "\r" in buffer:
                        line, _, buffer = buffer.partition("\n")
                        parsed, _ = _parse_sse_line(line.rstrip("\r"))
                        if parsed is None:
                            continue
                        evs, _ = _process_stream_event(
                            parsed, content_parts, accumulated, reasoning_parts
                        )
                        for ev in evs:
                            yield ev
        content_str = "".join(content_parts)
        # Deduplicate by call_id as a safety net
        seen_call_ids: set[str] = set()
        tool_calls_list: list[dict] = []
        for i in sorted(accumulated.keys()):
            acc = accumulated[i]
            cid = acc.get("id") or f"call_{i}"
            if cid in seen_call_ids:
                continue
            seen_call_ids.add(cid)
            tool_calls_list.append({
                "id": cid,
                "type": "function",
                "function": {
                    "name": acc.get("function", {}).get("name", "unknown"),
                    "arguments": acc.get("function", {}).get("arguments", "{}"),
                },
            })
        if tool_calls_list:
            yield StreamToolCallsEvent(
                type="tool_calls",
                tool_calls=cast(list[StreamToolCall], tool_calls_list),
            )
        finish_reason = "tool_calls" if tool_calls_list else "stop"
        yield StreamFinishEvent(type="finish", reason=finish_reason, content=content_str)
