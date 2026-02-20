from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.services.memory.observational.background import OMBackgroundRunner


class _DummySessionContext:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


def _session_factory():
    return _DummySessionContext()


class _EventCollector:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def publish(self, _chat_id: str, event: dict) -> dict:
        self.events.append(event)
        return event


def test_observation_skip_emits_terminal_status(monkeypatch) -> None:
    class FakeRepo:
        def __init__(self, _session) -> None:
            pass

        def list_messages(self, _chat_id: str):
            return [SimpleNamespace(role="user", content="hello", id="msg-1", timestamp="2026-02-20T00:00:00+00:00")]

        def get_latest_observation(self, _chat_id: str):
            return None

        def list_tool_calls(self, _chat_id: str):
            return []

        def list_reasoning_blocks(self, _chat_id: str):
            return []

    class FakeSvc:
        def __init__(self, _repo) -> None:
            pass

        def get_unobserved_messages(self, _messages, _latest_obs):
            return [], [{"role": "user", "content": "hello", "_message_id": "msg-1"}]

        async def run_observer(self, **_kwargs):
            raise AssertionError("Observer should not run when threshold is not met")

    import app.db.repositories.chat_repo as chat_repo_module
    import app.services.memory.observational.background as bg_module

    monkeypatch.setattr(chat_repo_module, "ChatRepository", FakeRepo)
    monkeypatch.setattr(bg_module, "ObservationMemoryService", FakeSvc)
    monkeypatch.setattr(bg_module, "count_messages_tokens", lambda _messages: 12)

    runner = OMBackgroundRunner()
    bus = _EventCollector()

    asyncio.run(
        runner._run_observation_cycle(
            chat_id="chat-1",
            model="model",
            observer_model=None,
            reflector_model=None,
            observer_threshold=30,
            reflector_threshold=50,
            client=object(),
            session_factory=_session_factory,
            event_bus=bus,
        )
    )

    statuses = [e["payload"]["status"] for e in bus.events if e.get("type") == "observation_status"]
    assert statuses == ["observed"]


def test_reflector_none_still_emits_reflected(monkeypatch) -> None:
    class FakeRepo:
        def __init__(self, _session) -> None:
            pass

        def list_messages(self, _chat_id: str):
            return [SimpleNamespace(role="user", content="hello", id="msg-1", timestamp="2026-02-20T00:00:00+00:00")]

        def get_latest_observation(self, _chat_id: str):
            return None

        def list_tool_calls(self, _chat_id: str):
            return []

        def list_reasoning_blocks(self, _chat_id: str):
            return []

    class FakeSvc:
        def __init__(self, _repo) -> None:
            pass

        def get_unobserved_messages(self, _messages, _latest_obs):
            return [], [{"role": "user", "content": "hello", "_message_id": "msg-1"}]

        async def run_observer(self, **_kwargs):
            return SimpleNamespace(token_count=80)

        async def run_reflector(self, **_kwargs):
            return None

    import app.db.repositories.chat_repo as chat_repo_module
    import app.services.memory.observational.background as bg_module

    monkeypatch.setattr(chat_repo_module, "ChatRepository", FakeRepo)
    monkeypatch.setattr(bg_module, "ObservationMemoryService", FakeSvc)
    monkeypatch.setattr(bg_module, "count_messages_tokens", lambda _messages: 120)

    runner = OMBackgroundRunner()
    bus = _EventCollector()

    asyncio.run(
        runner._run_observation_cycle(
            chat_id="chat-1",
            model="model",
            observer_model=None,
            reflector_model=None,
            observer_threshold=30,
            reflector_threshold=40,
            client=object(),
            session_factory=_session_factory,
            event_bus=bus,
        )
    )

    statuses = [e["payload"]["status"] for e in bus.events if e.get("type") == "observation_status"]
    assert statuses == ["observing", "observed", "reflecting", "reflected"]


def test_tool_activity_can_trigger_observer(monkeypatch) -> None:
    called = {"observer": 0}

    class FakeRepo:
        def __init__(self, _session) -> None:
            pass

        def list_messages(self, _chat_id: str):
            return [SimpleNamespace(role="user", content="hi", id="msg-1", timestamp="2026-02-20T00:00:00+00:00")]

        def get_latest_observation(self, _chat_id: str):
            return None

        def list_tool_calls(self, _chat_id: str):
            return [
                SimpleNamespace(
                    name="read_file",
                    input_json='{"path":"README.md"}',
                    output_text="x" * 600,
                    timestamp="2026-02-20T00:01:00+00:00",
                )
            ]

        def list_reasoning_blocks(self, _chat_id: str):
            return []

    class FakeSvc:
        def __init__(self, _repo) -> None:
            pass

        def get_unobserved_messages(self, _messages, _latest_obs):
            return [], list(_messages)

        async def run_observer(self, **_kwargs):
            called["observer"] += 1
            return None

    import app.db.repositories.chat_repo as chat_repo_module
    import app.services.memory.observational.background as bg_module

    monkeypatch.setattr(chat_repo_module, "ChatRepository", FakeRepo)
    monkeypatch.setattr(bg_module, "ObservationMemoryService", FakeSvc)
    monkeypatch.setattr(
        bg_module,
        "count_messages_tokens",
        lambda messages: 20 if any(m.get("role") == "tool" for m in messages) else 1,
    )

    runner = OMBackgroundRunner()
    bus = _EventCollector()

    asyncio.run(
        runner._run_observation_cycle(
            chat_id="chat-1",
            model="model",
            observer_model=None,
            reflector_model=None,
            observer_threshold=10,
            reflector_threshold=40,
            client=object(),
            session_factory=_session_factory,
            event_bus=bus,
        )
    )

    statuses = [e["payload"]["status"] for e in bus.events if e.get("type") == "observation_status"]
    assert statuses == ["observing", "observed"]
    assert called["observer"] == 1


def test_schedule_coalesces_and_reruns_latest(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_cycle(self, **kwargs):
        calls.append(kwargs["model"])
        await asyncio.sleep(0.03)

    monkeypatch.setattr(
        OMBackgroundRunner,
        "_run_observation_cycle",
        fake_cycle,
    )

    async def _scenario() -> None:
        runner = OMBackgroundRunner()
        bus = _EventCollector()

        runner.schedule_observation(
            chat_id="chat-1",
            model="m1",
            observer_model=None,
            reflector_model=None,
            observer_threshold=10,
            reflector_threshold=40,
            client=object(),
            session_factory=_session_factory,
            event_bus=bus,
        )
        await asyncio.sleep(0.001)

        # While m1 is still running, queue a newer request.
        runner.schedule_observation(
            chat_id="chat-1",
            model="m2",
            observer_model=None,
            reflector_model=None,
            observer_threshold=10,
            reflector_threshold=40,
            client=object(),
            session_factory=_session_factory,
            event_bus=bus,
        )

        await asyncio.sleep(0.08)
        assert calls == ["m1", "m2"]

    asyncio.run(_scenario())


def test_cancel_clears_pending_reschedule(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_cycle(self, **kwargs):
        calls.append(kwargs["model"])
        await asyncio.sleep(0.2)

    monkeypatch.setattr(
        OMBackgroundRunner,
        "_run_observation_cycle",
        fake_cycle,
    )

    async def _scenario() -> None:
        runner = OMBackgroundRunner()
        bus = _EventCollector()

        runner.schedule_observation(
            chat_id="chat-1",
            model="m1",
            observer_model=None,
            reflector_model=None,
            observer_threshold=10,
            reflector_threshold=40,
            client=object(),
            session_factory=_session_factory,
            event_bus=bus,
        )
        await asyncio.sleep(0.001)

        runner.schedule_observation(
            chat_id="chat-1",
            model="m2",
            observer_model=None,
            reflector_model=None,
            observer_threshold=10,
            reflector_threshold=40,
            client=object(),
            session_factory=_session_factory,
            event_bus=bus,
        )
        runner.cancel("chat-1")
        await asyncio.sleep(0.05)
        assert calls == ["m1"]

    asyncio.run(_scenario())


def test_cancel_route_cancels_observation_runner(client, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "app.services.chat_service.get_om_background_runner",
        lambda: SimpleNamespace(cancel=lambda chat_id: calls.append(chat_id)),
    )

    response = client.post("/api/chat/chat-1/cancel")
    assert response.status_code == 200
    assert calls == ["chat-1"]


def test_revert_route_cancels_observation_runner(client, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "app.services.revert_service.get_om_background_runner",
        lambda: SimpleNamespace(cancel=lambda chat_id: calls.append(chat_id)),
    )

    response = client.post("/api/chat/chat-1/revert/cp-1")
    assert response.status_code == 200
    assert calls == ["chat-1"]


def test_edit_message_cancels_observation_runner(client, monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr("app.services.chat_service._schedule_background_task", lambda **_kwargs: None)
    monkeypatch.setattr(
        "app.services.chat_service.get_om_background_runner",
        lambda: SimpleNamespace(cancel=lambda chat_id: calls.append(chat_id)),
    )

    seed = client.post(
        "/api/chat/chat-1/messages",
        json={"content": "seed message for edit"},
    )
    assert seed.status_code == 200
    message_id = seed.json()["data"]["message"]["id"]
    calls.clear()

    response = client.put(
        f"/api/chat/chat-1/messages/{message_id}",
        json={"content": "edited content"},
    )
    assert response.status_code == 200
    assert calls
    assert all(chat_id == "chat-1" for chat_id in calls)
