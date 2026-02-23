import asyncio
import ssl

import httpx
import pytest

from app.providers.openai_sub.client import _messages_to_codex_input
from app.providers.openai_sub.client import OpenAISubClient


def test_messages_to_codex_input_keeps_matched_tool_output() -> None:
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path":"a.txt"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_123", "content": "hello"},
    ]

    input_items, _ = _messages_to_codex_input(messages)

    assert input_items == [
        {
            "type": "function_call",
            "call_id": "call_123",
            "name": "read_file",
            "arguments": '{"path":"a.txt"}',
        },
        {
            "type": "function_call_output",
            "call_id": "call_123",
            "output": "hello",
        },
    ]


def test_messages_to_codex_input_drops_orphan_tool_output() -> None:
    messages = [
        {"role": "tool", "tool_call_id": "call_orphan", "content": "orphan output"}
    ]

    input_items, _ = _messages_to_codex_input(messages)

    assert input_items == []


class _RaiseOnEnterStream:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def __aenter__(self):
        raise self._exc

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeResponseStream:
    def __init__(
        self,
        *,
        chunks: list[bytes],
        status_code: int = 200,
        err_body: bytes = b"",
        raise_after_chunk_idx: int | None = None,
    ) -> None:
        self._chunks = chunks
        self.status_code = status_code
        self._err_body = err_body
        self._raise_after_chunk_idx = raise_after_chunk_idx
        self._request = httpx.Request("POST", "https://chatgpt.com/backend-api/codex/responses")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def aread(self) -> bytes:
        return self._err_body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = httpx.Response(
                self.status_code,
                request=self._request,
                content=self._err_body,
            )
            raise httpx.HTTPStatusError("upstream error", request=self._request, response=response)

    async def aiter_bytes(self, chunk_size: int = 1024):
        for idx, chunk in enumerate(self._chunks):
            yield chunk
            if self._raise_after_chunk_idx is not None and idx == self._raise_after_chunk_idx:
                raise httpx.ReadError("stream interrupted", request=self._request)


class _FakeAsyncClient:
    def __init__(self, scenarios: list[object]) -> None:
        self._scenarios = scenarios

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    def stream(self, method: str, url: str, headers=None, json=None):  # noqa: ANN001
        if not self._scenarios:
            raise AssertionError("Unexpected extra stream() call")
        return self._scenarios.pop(0)


def test_openai_sub_stream_retries_read_error_before_first_event(monkeypatch) -> None:
    request = httpx.Request("POST", "https://chatgpt.com/backend-api/codex/responses")
    scenarios: list[object] = [
        _RaiseOnEnterStream(httpx.ReadError("network read failed", request=request)),
        _FakeResponseStream(
            chunks=[
                b'data: {"type":"response.output_text.delta","delta":"Hello"}\n',
                b"data: [DONE]\n",
            ]
        ),
    ]

    monkeypatch.setattr(
        "app.providers.openai_sub.client.RETRY_DELAYS",
        (0,),
    )
    monkeypatch.setattr(
        "app.providers.openai_sub.client.httpx.AsyncClient",
        lambda timeout: _FakeAsyncClient(scenarios),
    )

    client = OpenAISubClient("token")

    async def _collect() -> list[dict]:
        events: list[dict] = []
        async for ev in client.create_chat_completion_stream(
            model="gpt-5.1-codex-mini",
            messages=[{"role": "user", "content": "hello"}],
        ):
            events.append(ev)
        return events

    events = asyncio.run(_collect())
    assert [e["type"] for e in events] == ["content", "finish"]
    assert events[0]["delta"] == "Hello"
    assert events[1]["content"] == "Hello"
    assert scenarios == []


def test_openai_sub_stream_retries_ssl_error_before_first_event(monkeypatch) -> None:
    scenarios: list[object] = [
        _RaiseOnEnterStream(
            ssl.SSLError("[SSL: SSLV3_ALERT_BAD_RECORD_MAC] sslv3 alert bad record mac")
        ),
        _FakeResponseStream(
            chunks=[
                b'data: {"type":"response.output_text.delta","delta":"Hello"}\n',
                b"data: [DONE]\n",
            ]
        ),
    ]

    monkeypatch.setattr(
        "app.providers.openai_sub.client.RETRY_DELAYS",
        (0,),
    )
    monkeypatch.setattr(
        "app.providers.openai_sub.client.httpx.AsyncClient",
        lambda timeout: _FakeAsyncClient(scenarios),
    )

    client = OpenAISubClient("token")

    async def _collect() -> list[dict]:
        events: list[dict] = []
        async for ev in client.create_chat_completion_stream(
            model="gpt-5.1-codex-mini",
            messages=[{"role": "user", "content": "hello"}],
        ):
            events.append(ev)
        return events

    events = asyncio.run(_collect())
    assert [e["type"] for e in events] == ["content", "finish"]
    assert events[0]["delta"] == "Hello"
    assert events[1]["content"] == "Hello"
    assert scenarios == []


def test_openai_sub_stream_does_not_retry_after_partial_output(monkeypatch) -> None:
    scenarios: list[object] = [
        _FakeResponseStream(
            chunks=[b'data: {"type":"response.output_text.delta","delta":"Hi"}\n'],
            raise_after_chunk_idx=0,
        ),
        _FakeResponseStream(chunks=[b"data: [DONE]\n"]),
    ]

    monkeypatch.setattr(
        "app.providers.openai_sub.client.RETRY_DELAYS",
        (0,),
    )
    monkeypatch.setattr(
        "app.providers.openai_sub.client.httpx.AsyncClient",
        lambda timeout: _FakeAsyncClient(scenarios),
    )

    client = OpenAISubClient("token")

    async def _collect() -> None:
        async for _ev in client.create_chat_completion_stream(
            model="gpt-5.1-codex-mini",
            messages=[{"role": "user", "content": "hello"}],
        ):
            pass

    with pytest.raises(httpx.ReadError):
        asyncio.run(_collect())

    # First scenario consumed; second remains, proving no retry after partial emission.
    assert len(scenarios) == 1
