import asyncio

import httpx
import pytest

from app.mcp.transports.http_transport import HttpTransport


def test_extract_json_from_sse_event_message_payload() -> None:
    body = (
        "event: message\r\n"
        "data: {\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"ok\":true}}\r\n\r\n"
    )
    parsed = HttpTransport._extract_json_from_sse(body)
    assert parsed == {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}


def test_extract_json_from_sse_multiline_data_payload() -> None:
    body = (
        "event: message\n"
        "data: {\"jsonrpc\":\"2.0\",\n"
        "data: \"id\":1,\n"
        "data: \"result\":{\"ok\":true}}\n\n"
    )
    parsed = HttpTransport._extract_json_from_sse(body)
    assert parsed == {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}


def test_post_accepts_sse_when_json_load_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    body = (
        "event: message\r\n"
        "data: {\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"serverInfo\":{\"name\":\"Dosu MCP\"}}}\r\n\r\n"
    )

    async def fake_post(self, url, json, headers):  # noqa: ANN001
        return httpx.Response(
            200,
            text=body,
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    transport = HttpTransport({"url": "https://api.dosu.dev/v1/mcp"})
    result = asyncio.run(transport._post({"jsonrpc": "2.0", "id": 1, "method": "initialize"}))
    assert result == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"serverInfo": {"name": "Dosu MCP"}},
    }


def test_post_allows_empty_body_for_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self, url, json, headers):  # noqa: ANN001
        return httpx.Response(
            202,
            text="",
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    transport = HttpTransport({"url": "https://api.dosu.dev/v1/mcp"})
    result = asyncio.run(
        transport._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            allow_empty_response=True,
        )
    )
    assert result is None


def test_post_rejects_empty_body_for_request_response(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self, url, json, headers):  # noqa: ANN001
        return httpx.Response(
            202,
            text="",
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    transport = HttpTransport({"url": "https://api.dosu.dev/v1/mcp"})
    with pytest.raises(RuntimeError, match="Empty response"):
        asyncio.run(transport._post({"jsonrpc": "2.0", "id": 1, "method": "initialize"}))
