import json
import time
import asyncio

from app.db.session import get_sessionmaker
from app.services.event_bus import get_event_bus


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


def test_approve_reject_transitions(client) -> None:
    send = client.post("/api/chat/chat-1/messages", json={"content": "approve/reject seed"}).json()["data"]
    history = client.get("/api/chat/chat-1/history").json()["data"]
    checkpoint_id = send["checkpoint"]["id"]
    pending = [t for t in history["toolCalls"] if t.get("status") == "pending"]
    pending_for_checkpoint = [t for t in pending if t.get("input", {}).get("path") == "plans/backend-python-mvp-plan.md"]
    assert pending_for_checkpoint
    approve_id = pending_for_checkpoint[-1]["id"]

    approve_res = client.post(f"/api/chat/chat-1/approve", json={"toolCallId": approve_id})
    assert approve_res.status_code == 200
    approve_data = approve_res.json()["data"]
    assert approve_data["toolCall"]["status"] in {"completed", "error"}

    send2 = client.post("/api/chat/chat-1/messages", json={"content": "reject seed"}).json()["data"]
    history2 = client.get("/api/chat/chat-1/history").json()["data"]
    pending2 = [t for t in history2["toolCalls"] if t.get("status") == "pending"]
    reject_id = pending2[-1]["id"]
    reject_res = client.post(f"/api/chat/chat-1/reject", json={"toolCallId": reject_id, "reason": "deny"})
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
        send = client.post("/api/chat/chat-1/messages", json={"content": "file edit seed"}).json()["data"]
        tool_calls = client.get("/api/chat/chat-1/history").json()["data"]["toolCalls"]
        pending = [t for t in tool_calls if t["status"] == "pending"]
        if pending:
            client.post(f"/api/chat/chat-1/approve", json={"toolCallId": pending[-1]["id"]})
        history = client.get("/api/chat/chat-1/history").json()["data"]

    if history["fileEdits"]:
        file_edit_id = history["fileEdits"][-1]["id"]
        response = client.post(f"/api/chat/chat-1/revert-file/{file_edit_id}")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["removedFileEditId"] == file_edit_id
        assert all(f["id"] != file_edit_id for f in payload["fileEdits"])


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
