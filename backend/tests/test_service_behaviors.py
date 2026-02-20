import asyncio
import json

import httpx

import app.services.chat_service as chat_service_module
from app.db.repositories.chat_repo import ChatRepository
from app.db.session import get_sessionmaker
from app.services.event_bus import get_event_bus
from app.utils.time import utc_now_iso


def _assert_envelope(payload: dict) -> None:
    assert isinstance(payload.get("ok"), bool)
    assert "timestamp" in payload


def test_send_message_checkpoint_persistence(client) -> None:
    response = client.post("/api/chat/chat-1/messages", json={"content": "phase3 send message"})
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["ok"] is True
    data = body["data"]
    assert "message" in data
    assert "checkpoint" in data
    assert data["message"]["checkpointId"] == data["checkpoint"]["id"]

    history = client.get("/api/chat/chat-1/history").json()["data"]
    assert any(m["id"] == data["message"]["id"] for m in history["messages"])
    assert any(c["id"] == data["checkpoint"]["id"] for c in history["checkpoints"])


def test_auto_approve_rule_matcher_fields(client) -> None:
    set_rules = client.put(
        "/api/settings/auto-approve",
        json={
            "rules": [
                {"field": "tool", "value": "read_file", "enabled": True},
                {"field": "path", "value": "plans/backend-python-mvp-plan.md", "enabled": True},
                {"field": "extension", "value": ".md", "enabled": True},
                {"field": "directory", "value": "plans", "enabled": True},
                {"field": "pattern", "value": "backend-python", "enabled": True},
            ]
        },
    )
    assert set_rules.status_code == 200
    body = set_rules.json()
    _assert_envelope(body)
    assert len(body["data"]["rules"]) == 5

    get_rules = client.get("/api/settings/auto-approve")
    assert get_rules.status_code == 200
    data = get_rules.json()["data"]
    assert len(data["rules"]) == 5
    fields = {r["field"] for r in data["rules"]}
    assert fields == {"tool", "path", "extension", "directory", "pattern"}


def test_reasoning_level_round_trip(client) -> None:
    set_level = client.put(
        "/api/settings/reasoning-level",
        json={"reasoningLevel": "high"},
    )
    assert set_level.status_code == 200
    body = set_level.json()
    _assert_envelope(body)
    assert body["data"]["reasoningLevel"] == "high"

    settings = client.get("/api/settings")
    assert settings.status_code == 200
    settings_data = settings.json()["data"]
    assert settings_data["reasoningLevel"] == "high"

    set_off = client.put(
        "/api/settings/reasoning-level",
        json={"reasoningLevel": "off"},
    )
    assert set_off.status_code == 200
    assert set_off.json()["data"]["reasoningLevel"] == "off"


def test_approve_reject_transitions(client) -> None:
    approve_id = "tc-svc-approve"
    with get_sessionmaker()() as db:
        repo = ChatRepository(db)
        repo.create_tool_call(
            tool_call_id=approve_id,
            chat_id="chat-1",
            checkpoint_id="cp-1",
            name="read_file",
            status="pending",
            input_json='{"path": "/Users/darkeden/Scythe-Agent/backend/pyproject.toml"}',
            timestamp=utc_now_iso(),
            parallel_group=None,
        )
        db.commit()

    approve_res = client.post("/api/chat/chat-1/approve", json={"toolCallId": approve_id})
    assert approve_res.status_code == 200
    approve_data = approve_res.json()["data"]
    assert approve_data["toolCall"]["status"] in {"completed", "error"}

    reject_id = "tc-svc-reject"
    with get_sessionmaker()() as db:
        repo = ChatRepository(db)
        repo.create_tool_call(
            tool_call_id=reject_id,
            chat_id="chat-1",
            checkpoint_id="cp-1",
            name="read_file",
            status="pending",
            input_json='{"path": "/Users/darkeden/Scythe-Agent/backend/pyproject.toml"}',
            timestamp=utc_now_iso(),
            parallel_group=None,
        )
        db.commit()
    reject_res = client.post("/api/chat/chat-1/reject", json={"toolCallId": reject_id, "reason": "deny"})
    assert reject_res.status_code == 200
    reject_data = reject_res.json()["data"]
    assert reject_data["status"] == "rejected"
    assert reject_data["toolCallId"] == reject_id


def test_summarize_reduces_tokens(client) -> None:
    before = client.get("/api/chat/chat-1/history").json()["data"]
    before_tokens = sum(i["tokens"] for i in before["contextItems"])
    response = client.post("/api/chat/chat-1/summarize")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["tokensBefore"] == before_tokens
    assert payload["tokensAfter"] <= payload["tokensBefore"]


def test_revert_consistency(client) -> None:
    sent = client.post("/api/chat/chat-1/messages", json={"content": "revert consistency"}).json()["data"]
    checkpoint_id = sent["checkpoint"]["id"]

    reverted = client.post(f"/api/chat/chat-1/revert/{checkpoint_id}")
    assert reverted.status_code == 200
    data = reverted.json()["data"]
    assert all("id" in m for m in data["messages"])
    assert all("id" in c for c in data["checkpoints"])

    history = client.get("/api/chat/chat-1/history").json()["data"]
    assert len(history["messages"]) == len(data["messages"])


def test_revert_file_consistency(client) -> None:
    history = client.get("/api/chat/chat-1/history").json()["data"]
    if not history["fileEdits"]:
        client.post("/api/chat/chat-1/messages", json={"content": "file edit seed"}).json()["data"]
        tool_calls = client.get("/api/chat/chat-1/history").json()["data"]["toolCalls"]
        pending = [t for t in tool_calls if t["status"] == "pending"]
        if pending:
            client.post("/api/chat/chat-1/approve", json={"toolCallId": pending[-1]["id"]})
        history = client.get("/api/chat/chat-1/history").json()["data"]

    if history["fileEdits"]:
        file_edit_id = history["fileEdits"][-1]["id"]
        response = client.post(f"/api/chat/chat-1/revert-file/{file_edit_id}")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["removedFileEditId"] == file_edit_id
        assert all(f["id"] != file_edit_id for f in payload["fileEdits"])


def test_revert_prunes_observational_memory_to_checkpoint(client) -> None:
    base_ts = "2099-01-01T00:00:00.000000+00:00"
    later_ts = "2099-01-01T00:05:00.000000+00:00"

    with get_sessionmaker()() as db:
        repo = ChatRepository(db)

        keep_message = repo.create_message(
            message_id="msg-obs-keep",
            chat_id="chat-1",
            role="user",
            content="keep memory message",
            timestamp=base_ts,
            checkpoint_id=None,
        )
        keep_checkpoint = repo.create_checkpoint(
            checkpoint_id="cp-obs-keep",
            chat_id="chat-1",
            message_id=keep_message.id,
            label="keep checkpoint",
            timestamp=base_ts,
        )
        repo.link_message_checkpoint(keep_message, keep_checkpoint.id)

        drop_message = repo.create_message(
            message_id="msg-obs-drop",
            chat_id="chat-1",
            role="user",
            content="drop memory message",
            timestamp=later_ts,
            checkpoint_id=None,
        )
        drop_checkpoint = repo.create_checkpoint(
            checkpoint_id="cp-obs-drop",
            chat_id="chat-1",
            message_id=drop_message.id,
            label="drop checkpoint",
            timestamp=later_ts,
        )
        repo.link_message_checkpoint(drop_message, drop_checkpoint.id)

        repo.create_observation(
            observation_id="obs-keep",
            chat_id="chat-1",
            generation=0,
            content="keep observation",
            token_count=3,
            trigger_token_count=11,
            observed_up_to_message_id=keep_message.id,
            current_task="keep task",
            suggested_response="keep suggestion",
            timestamp=base_ts,
        )
        repo.create_observation(
            observation_id="obs-drop",
            chat_id="chat-1",
            generation=1,
            content="drop observation",
            token_count=3,
            trigger_token_count=13,
            observed_up_to_message_id=drop_message.id,
            current_task="drop task",
            suggested_response="drop suggestion",
            timestamp=later_ts,
        )
        repo.set_memory_state(
            chat_id="chat-1",
            strategy="observational",
            state_json=json.dumps(
                {
                    "generation": 1,
                    "tokenCount": 3,
                    "observedUpToMessageId": drop_message.id,
                    "currentTask": "drop task",
                    "suggestedResponse": "drop suggestion",
                    "timestamp": later_ts,
                    "content": "drop observation",
                    "buffer": {
                        "tokens": 1024,
                        "lastBoundary": 4,
                        "upToMessageId": drop_message.id,
                        "upToTimestamp": later_ts,
                        "chunks": [
                            {
                                "content": "keep chunk",
                                "tokenCount": 2,
                                "observedUpToMessageId": keep_message.id,
                                "observedUpToTimestamp": base_ts,
                            },
                            {
                                "content": "drop chunk",
                                "tokenCount": 2,
                                "observedUpToMessageId": drop_message.id,
                                "observedUpToTimestamp": later_ts,
                            },
                        ],
                    },
                }
            ),
            updated_at=later_ts,
        )
        db.commit()

    revert_res = client.post("/api/chat/chat-1/revert/cp-obs-keep")
    assert revert_res.status_code == 200

    memory_res = client.get("/api/chat/chat-1/memory")
    assert memory_res.status_code == 200
    memory = memory_res.json()["data"]
    assert memory["hasMemoryState"] is True

    observations = memory["observations"]
    assert [o["id"] for o in observations] == ["obs-keep"]
    assert observations[0]["triggerTokenCount"] == 11

    state = memory["state"]
    assert state["observedUpToMessageId"] == "msg-obs-keep"
    assert state["content"] == "keep observation"
    assert state["triggerTokenCount"] == 11
    assert state["timestamp"] == base_ts
    assert state["buffer"]["lastBoundary"] == 0

    chunks = state["buffer"]["chunks"]
    assert len(chunks) == 1
    assert chunks[0]["content"] == "keep chunk"
    assert chunks[0]["observedUpToMessageId"] == "msg-obs-keep"


def test_sse_ordering_and_disconnect_cleanup(client) -> None:
    event_bus = get_event_bus()

    async def _exercise_bus() -> tuple[dict, dict, int]:
        q = await event_bus.subscribe("chat-1")
        count_before = await event_bus.subscriber_count("chat-1")
        first = await event_bus.publish("chat-1", {"type": "message", "payload": {"message": {"id": "m"}}})
        second = await event_bus.publish("chat-1", {"type": "checkpoint", "payload": {"checkpoint": {"id": "c"}}})
        got1 = await asyncio.wait_for(q.get(), timeout=1)
        got2 = await asyncio.wait_for(q.get(), timeout=1)
        await event_bus.unsubscribe("chat-1", q)
        count_after = await event_bus.subscriber_count("chat-1")
        assert got1["type"] == first["type"]
        assert got2["type"] == second["type"]
        return first, second, count_before - count_after

    first, second, delta = asyncio.run(_exercise_bus())
    assert first["type"] == "message"
    assert second["type"] == "checkpoint"
    assert first["sequence"] < second["sequence"]
    assert delta >= 1


def test_continue_agent_schedules_latest_checkpoint(client, monkeypatch) -> None:
    captured: dict[str, str] = {}
    history_before = client.get("/api/chat/chat-1/history").json()["data"]
    latest_checkpoint = history_before["checkpoints"][-1]["id"]
    message_by_id = {m["id"]: m["content"] for m in history_before["messages"]}
    latest_checkpoint_message_id = history_before["checkpoints"][-1]["messageId"]
    expected_content = message_by_id.get(latest_checkpoint_message_id, "")

    def _fake_schedule_background_task(
        *,
        chat_id: str,
        checkpoint_id: str,
        content: str,
        session_factory,
        event_bus,
        task_manager,
    ) -> None:
        captured["chat_id"] = chat_id
        captured["checkpoint_id"] = checkpoint_id
        captured["content"] = content

    monkeypatch.setattr(chat_service_module, "_schedule_background_task", _fake_schedule_background_task)

    response = client.post("/api/chat/chat-1/continue")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    data = body["data"]
    assert data["started"] is True
    assert data["checkpointId"] == latest_checkpoint
    assert captured["chat_id"] == "chat-1"
    assert captured["checkpoint_id"] == latest_checkpoint
    assert captured["content"] == expected_content


def test_format_runtime_error_http_status_includes_provider_detail() -> None:
    request = httpx.Request("POST", "https://chatgpt.com/backend-api/codex/responses")
    response = httpx.Response(
        400,
        request=request,
        json={
            "error": {
                "message": "No tool call found for function call output with call_id call_123.",
                "type": "invalid_request_error",
                "param": "input",
            }
        },
    )
    exc = httpx.HTTPStatusError("bad request", request=request, response=response)

    formatted = chat_service_module._format_runtime_error(exc)

    assert "Upstream request failed (400)" in formatted
    assert "https://chatgpt.com/backend-api/codex/responses" in formatted
    assert "No tool call found for function call output with call_id call_123." in formatted
    assert "type=invalid_request_error" in formatted
    assert "param=input" in formatted


def test_format_runtime_error_non_http_uses_exception_message() -> None:
    formatted = chat_service_module._format_runtime_error(RuntimeError("boom"))
    assert formatted == "boom"
