from app.db.repositories.chat_repo import ChatRepository
from app.db.session import get_sessionmaker
from app.services.plan_file_store import PlanFileStore
from app.services import chat_service as chat_service_module
from app.utils.time import utc_now_iso


def _seed_plan(*, plan_id: str, chat_id: str = "chat-1", content: str = "# Plan\n\nInitial") -> None:
    with get_sessionmaker()() as db:
        repo = ChatRepository(db)
        chat = repo.get_chat(chat_id)
        assert chat is not None
        store = PlanFileStore()
        path, sha = store.write_plan(project_id=chat.project_id, plan_id=plan_id, content=content)
        now = utc_now_iso()
        repo.create_project_plan(
            plan_id=plan_id,
            chat_id=chat_id,
            project_id=chat.project_id,
            checkpoint_id=None,
            title="Implementation Plan",
            status="ready",
            file_path=str(path),
            revision=1,
            content_sha256=sha,
            last_editor="agent",
            approved_action=None,
            implementation_chat_id=None,
            created_at=now,
            updated_at=now,
        )
        db.commit()


def test_plan_list_get_update_with_conflict(client) -> None:
    plan_id = "plan-endpoint-crud"
    _seed_plan(plan_id=plan_id)

    list_res = client.get("/api/chat/chat-1/plans")
    assert list_res.status_code == 200
    listed = list_res.json()["data"]["plans"]
    assert any(plan["id"] == plan_id for plan in listed)

    get_res = client.get(f"/api/chat/chat-1/plans/{plan_id}")
    assert get_res.status_code == 200
    assert get_res.json()["data"]["plan"]["id"] == plan_id

    update_res = client.put(
        f"/api/chat/chat-1/plans/{plan_id}",
        json={"content": "# Plan\n\nUpdated", "baseRevision": 1, "lastEditor": "user"},
    )
    assert update_res.status_code == 200
    update_data = update_res.json()["data"]
    assert update_data["conflict"] is False
    assert update_data["plan"]["revision"] == 2

    stale_update = client.put(
        f"/api/chat/chat-1/plans/{plan_id}",
        json={"content": "# Plan\n\nStale", "baseRevision": 1, "lastEditor": "user"},
    )
    assert stale_update.status_code == 200
    stale_data = stale_update.json()["data"]
    assert stale_data["conflict"] is True


def test_plan_approve_actions_schedule_implementation(client, monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    def _fake_schedule_background_task(
        *,
        chat_id: str,
        checkpoint_id: str,
        content: str,
        mode: str,
        active_plan_id: str | None,
        session_factory,
        event_bus,
        task_manager,
    ) -> None:
        captured["chat_id"] = chat_id
        captured["checkpoint_id"] = checkpoint_id
        captured["content"] = content
        captured["mode"] = mode
        captured["active_plan_id"] = active_plan_id

    monkeypatch.setattr(chat_service_module, "_schedule_background_task", _fake_schedule_background_task)

    keep_plan = "plan-approve-keep"
    _seed_plan(plan_id=keep_plan)
    keep_res = client.post(
        f"/api/chat/chat-1/plans/{keep_plan}/approve",
        json={"action": "keep_context"},
    )
    assert keep_res.status_code == 200
    keep_data = keep_res.json()["data"]
    assert keep_data["implementationChatId"] == "chat-1"
    assert keep_data["plan"]["status"] == "implementing"
    assert captured["chat_id"] == "chat-1"
    assert captured["mode"] == "default"
    assert captured["active_plan_id"] is None

    clear_plan = "plan-approve-clear"
    _seed_plan(plan_id=clear_plan)
    clear_res = client.post(
        f"/api/chat/chat-1/plans/{clear_plan}/approve",
        json={"action": "clear_context"},
    )
    assert clear_res.status_code == 200
    clear_data = clear_res.json()["data"]
    assert clear_data["implementationChatId"] is not None
    assert clear_data["implementationChatId"] != "chat-1"
    assert clear_data["plan"]["status"] == "implementing"
    assert captured["chat_id"] == clear_data["implementationChatId"]
    assert captured["mode"] == "default"
    assert captured["active_plan_id"] is None
