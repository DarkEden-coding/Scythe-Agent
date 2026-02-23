import asyncio
import time

from app.db.repositories.chat_repo import ChatRepository
from app.db.session import get_sessionmaker
from app.utils.mappers import map_file_action_for_ui, map_role_for_ui
from app.services.event_bus import get_event_bus
from app.utils.time import utc_now_iso


def _assert_envelope(payload: dict) -> None:
    assert isinstance(payload.get("ok"), bool)
    assert "timestamp" in payload


def test_serializer_compatibility_mappings_explicit() -> None:
    assert map_role_for_ui("assistant") == "agent"
    assert map_role_for_ui("user") == "user"

    assert map_file_action_for_ui("created") == "create"
    assert map_file_action_for_ui("modified") == "edit"
    assert map_file_action_for_ui("deleted") == "delete"


def test_frontend_contract_change_model_shape(client) -> None:
    settings = client.get("/api/settings")
    assert settings.status_code == 200
    settings_payload = settings.json()
    _assert_envelope(settings_payload)
    models = settings_payload["data"]["availableModels"]
    assert models

    previous = settings_payload["data"]["model"]
    target = next((m for m in models if m != previous), previous)

    response = client.put("/api/settings/model", json={"model": target})
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["ok"] is True

    data = body["data"]
    assert set(data.keys()) == {"model", "previousModel", "contextLimit"}
    assert data["model"] == target
    assert isinstance(data["previousModel"], str)
    assert isinstance(data["contextLimit"], int)


def test_frontend_contract_action_envelopes_and_shapes(client) -> None:
    send = client.post("/api/chat/chat-1/messages", json={"content": "phase8 hardening contract"})
    assert send.status_code == 200
    send_body = send.json()
    _assert_envelope(send_body)
    send_data = send_body["data"]
    assert "message" in send_data
    assert "checkpoint" in send_data
    assert send_data["message"]["role"] in {"user", "agent"}

    history = client.get("/api/chat/chat-1/history")
    assert history.status_code == 200
    history_body = history.json()
    _assert_envelope(history_body)
    history_data = history_body["data"]
    assert isinstance(history_data["messages"], list)
    assert isinstance(history_data["toolCalls"], list)
    assert isinstance(history_data["fileEdits"], list)
    assert isinstance(history_data["plans"], list)

    tool_call_id = "tc-contract-approve"
    with get_sessionmaker()() as db:
        repo = ChatRepository(db)
        repo.create_tool_call(
            tool_call_id=tool_call_id,
            chat_id="chat-1",
            checkpoint_id="cp-1",
            name="read_file",
            status="pending",
            input_json='{"path": "/Users/darkeden/Scythe-Agent/backend/pyproject.toml"}',
            timestamp=utc_now_iso(),
            parallel_group=None,
        )
        db.commit()

    approve = client.post("/api/chat/chat-1/approve", json={"toolCallId": tool_call_id})
    assert approve.status_code == 200
    approve_body = approve.json()
    _assert_envelope(approve_body)
    approve_data = approve_body["data"]
    assert "toolCall" in approve_data
    assert "fileEdits" in approve_data
    assert approve_data["toolCall"]["id"] == tool_call_id
    assert approve_data["toolCall"]["status"] in {"completed", "error"}
    assert isinstance(approve_data["fileEdits"], list)

    reject_id = "tc-contract-reject"
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

    reject = client.post("/api/chat/chat-1/reject", json={"toolCallId": reject_id, "reason": "phase8"})
    assert reject.status_code == 200
    reject_body = reject.json()
    _assert_envelope(reject_body)
    reject_data = reject_body["data"]
    assert reject_data == {"toolCallId": reject_id, "status": "rejected"}


def test_sse_ordering_sequence_and_disconnect_cleanup_strict(client) -> None:
    event_bus = get_event_bus()

    async def _assert_ordering_and_cleanup() -> tuple[dict, dict, int, int]:
        queue = await event_bus.subscribe("chat-1")
        before = await event_bus.subscriber_count("chat-1")
        try:
            first = await event_bus.publish("chat-1", {"type": "message", "payload": {"message": {"id": "m1"}}})
            second = await event_bus.publish(
                "chat-1", {"type": "checkpoint", "payload": {"checkpoint": {"id": "c1"}}}
            )
            recv_first = await asyncio.wait_for(queue.get(), timeout=1)
            recv_second = await asyncio.wait_for(queue.get(), timeout=1)
            assert recv_first["type"] == "message"
            assert recv_second["type"] == "checkpoint"
            return first, second, before, await event_bus.subscriber_count("chat-1")
        finally:
            await event_bus.unsubscribe("chat-1", queue)

    first, second, before, during = asyncio.run(_assert_ordering_and_cleanup())
    assert first["sequence"] < second["sequence"]
    assert first["chatId"] == "chat-1"
    assert second["chatId"] == "chat-1"
    assert before >= 1
    assert during >= 1

    for _ in range(40):
        if asyncio.run(event_bus.subscriber_count("chat-1")) == 0:
            break
        time.sleep(0.025)
    assert asyncio.run(event_bus.subscriber_count("chat-1")) == 0
