from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast

from app.db.models.observation import Observation
from app.services.memory.observational.background import OMBackgroundRunner
from app.services.memory.observational.service import (
    BufferedObservationChunk,
    ObservationMemoryService,
)


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

        def get_observational_state(self, _chat_id: str, *, default_buffer_tokens: int):
            return {
                "buffer": {
                    "tokens": default_buffer_tokens,
                    "lastBoundary": 0,
                    "upToMessageId": None,
                    "upToTimestamp": None,
                    "chunks": [],
                }
            }

        def split_messages_by_waterline(self, _messages, **_kwargs):
            return [], list(_messages)

        def save_observational_state(self, *_args, **_kwargs):
            return None

        def update_state_from_observation(self, *, state, observation):
            return state

    import app.db.repositories.chat_repo as chat_repo_module
    import app.services.memory.observational.background as bg_module

    monkeypatch.setattr(chat_repo_module, "ChatRepository", FakeRepo)
    monkeypatch.setattr(bg_module, "ObservationMemoryService", FakeSvc)
    monkeypatch.setattr(bg_module, "count_messages_tokens", lambda _messages, **_kwargs: 12)

    runner = OMBackgroundRunner()
    bus = _EventCollector()

    asyncio.run(
        runner._run_observation_cycle(
            chat_id="chat-1",
            model="model",
            observer_model=None,
            reflector_model=None,
            observer_threshold=30,
            buffer_tokens=100,
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

        def get_observational_state(self, _chat_id: str, *, default_buffer_tokens: int):
            return {
                "buffer": {
                    "tokens": default_buffer_tokens,
                    "lastBoundary": 0,
                    "upToMessageId": None,
                    "upToTimestamp": None,
                    "chunks": [],
                }
            }

        def split_messages_by_waterline(self, _messages, **_kwargs):
            return [], list(_messages)

        def save_observational_state(self, *_args, **_kwargs):
            return None

        def update_state_from_observation(self, *, state, observation):
            return state

        async def run_observer_for_chunk(self, **_kwargs):
            return BufferedObservationChunk(
                content="summary",
                token_count=80,
                observed_up_to_message_id="msg-1",
                observed_up_to_timestamp="2026-02-20T00:01:00+00:00",
            )

        def activate_buffered_observations(self, **_kwargs):
            return SimpleNamespace(
                token_count=80,
                observed_up_to_message_id="msg-1",
                timestamp="2026-02-20T00:01:00+00:00",
            )

        async def run_reflector(self, **_kwargs):
            return None

    import app.db.repositories.chat_repo as chat_repo_module
    import app.services.memory.observational.background as bg_module

    monkeypatch.setattr(chat_repo_module, "ChatRepository", FakeRepo)
    monkeypatch.setattr(bg_module, "ObservationMemoryService", FakeSvc)
    monkeypatch.setattr(bg_module, "count_messages_tokens", lambda _messages, **_kwargs: 120)

    runner = OMBackgroundRunner()
    bus = _EventCollector()

    asyncio.run(
        runner._run_observation_cycle(
            chat_id="chat-1",
            model="model",
            observer_model=None,
            reflector_model=None,
            observer_threshold=30,
            buffer_tokens=6,
            reflector_threshold=40,
            client=object(),
            session_factory=_session_factory,
            event_bus=bus,
        )
    )

    statuses = [e["payload"]["status"] for e in bus.events if e.get("type") == "observation_status"]
    # Buffer phase doesn't fire (buffer_tokens clamped to 500 > 120 unobserved tokens),
    # so activation runs directly via fallback → observed → reflecting → reflected.
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

        def get_observational_state(self, _chat_id: str, *, default_buffer_tokens: int):
            return {
                "buffer": {
                    "tokens": default_buffer_tokens,
                    "lastBoundary": 0,
                    "upToMessageId": None,
                    "upToTimestamp": None,
                    "chunks": [],
                }
            }

        def split_messages_by_waterline(self, _messages, **_kwargs):
            return [], list(_messages)

        def save_observational_state(self, *_args, **_kwargs):
            return None

        def update_state_from_observation(self, *, state, observation):
            return state

        async def run_observer_for_chunk(self, **_kwargs):
            called["observer"] += 1
            return BufferedObservationChunk(
                content="summary",
                token_count=10,
                observed_up_to_message_id="msg-1",
                observed_up_to_timestamp="2026-02-20T00:01:00+00:00",
            )

        def activate_buffered_observations(self, **_kwargs):
            return SimpleNamespace(
                token_count=10,
                observed_up_to_message_id="msg-1",
                timestamp="2026-02-20T00:01:00+00:00",
            )

    import app.db.repositories.chat_repo as chat_repo_module
    import app.services.memory.observational.background as bg_module

    monkeypatch.setattr(chat_repo_module, "ChatRepository", FakeRepo)
    monkeypatch.setattr(bg_module, "ObservationMemoryService", FakeSvc)
    monkeypatch.setattr(
        bg_module,
        "count_messages_tokens",
        lambda messages, **_kwargs: 20 if any(m.get("role") == "tool" for m in messages) else 1,
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
            buffer_tokens=2,
            reflector_threshold=40,
            client=object(),
            session_factory=_session_factory,
            event_bus=bus,
        )
    )

    statuses = [e["payload"]["status"] for e in bus.events if e.get("type") == "observation_status"]
    # Buffer phase doesn't fire (buffer_tokens clamped to 500 > unobserved token count),
    # so activation runs directly via fallback → observed.
    assert statuses == ["observing", "observed"]
    assert called["observer"] == 1


def test_initial_information_counts_toward_observer_threshold(monkeypatch, tmp_path) -> None:
    called = {"observer": 0}
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "src" / "main.py").write_text("print('hi')", encoding="utf-8")

    class FakeRepo:
        def __init__(self, _session) -> None:
            pass

        def list_messages(self, _chat_id: str):
            return [SimpleNamespace(role="user", content="ok", id="msg-1", timestamp="2026-02-20T00:00:00+00:00")]

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
            return [], list(_messages)

        def get_observational_state(self, _chat_id: str, *, default_buffer_tokens: int):
            return {
                "buffer": {
                    "tokens": default_buffer_tokens,
                    "lastBoundary": 0,
                    "upToMessageId": None,
                    "upToTimestamp": None,
                    "chunks": [],
                }
            }

        def split_messages_by_waterline(self, _messages, **_kwargs):
            return [], list(_messages)

        def save_observational_state(self, *_args, **_kwargs):
            return None

        def update_state_from_observation(self, *, state, observation):
            return state

        async def run_observer_for_chunk(self, **_kwargs):
            called["observer"] += 1
            return BufferedObservationChunk(
                content="summary",
                token_count=10,
                observed_up_to_message_id="msg-1",
                observed_up_to_timestamp="2026-02-20T00:00:00+00:00",
            )

        def activate_buffered_observations(self, **_kwargs):
            return SimpleNamespace(
                token_count=10,
                observed_up_to_message_id="msg-1",
                timestamp="2026-02-20T00:00:00+00:00",
            )

    import app.db.repositories.chat_repo as chat_repo_module
    import app.services.memory.observational.background as bg_module

    monkeypatch.setattr(chat_repo_module, "ChatRepository", FakeRepo)
    monkeypatch.setattr(bg_module, "ObservationMemoryService", FakeSvc)
    monkeypatch.setattr(
        bg_module,
        "count_messages_tokens",
        lambda messages, **_kwargs: 100
        if any("Project root (absolute path):" in str(m.get("content", "")) for m in messages)
        else 1,
    )

    runner = OMBackgroundRunner()
    bus = _EventCollector()

    asyncio.run(
        runner._run_observation_cycle(
            chat_id="chat-1",
            model="model",
            project_path=str(tmp_path),
            observer_model=None,
            reflector_model=None,
            observer_threshold=50,
            buffer_tokens=6,
            reflector_threshold=200,
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
            buffer_tokens=2,
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
            buffer_tokens=2,
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
            buffer_tokens=2,
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
            buffer_tokens=2,
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


def test_split_messages_by_waterline_uses_timestamp_when_message_anchor_missing() -> None:
    svc = ObservationMemoryService(SimpleNamespace())
    messages = [
        {
            "role": "user",
            "content": "hello",
            "_message_id": "msg-1",
            "_timestamp": "2026-02-20T10:00:00+00:00",
        },
        {
            "role": "assistant",
            "content": "hi",
            "_message_id": "msg-2",
            "_timestamp": "2026-02-20T10:01:00+00:00",
        },
        {
            "role": "tool",
            "content": "tool output",
            "_timestamp": "2026-02-20T10:01:30+00:00",
        },
    ]

    observed, unobserved = svc.split_messages_by_waterline(
        messages,
        waterline_message_id="missing-anchor",
        waterline_timestamp="2026-02-20T10:01:00+00:00",
    )

    assert [m.get("_message_id") for m in observed] == ["msg-1", "msg-2"]
    assert [m.get("_message_id") for m in unobserved] == [None]


def test_split_messages_by_waterline_parses_z_suffix_timestamps() -> None:
    svc = ObservationMemoryService(SimpleNamespace())
    messages = [
        {
            "role": "user",
            "content": "hello",
            "_message_id": "msg-1",
            "_timestamp": "2026-02-20T10:00:00+00:00",
        },
        {
            "role": "assistant",
            "content": "hi",
            "_message_id": "msg-2",
            "_timestamp": "2026-02-20T10:01:00+00:00",
        },
    ]

    observed, unobserved = svc.split_messages_by_waterline(
        messages,
        waterline_message_id=None,
        waterline_timestamp="2026-02-20T10:01:00Z",
    )

    assert [m.get("_message_id") for m in observed] == ["msg-1", "msg-2"]
    assert unobserved == []


def test_activate_buffered_observations_starts_generation_at_zero() -> None:
    class FakeRepo:
        def get_latest_observation(self, _chat_id: str):
            return None

        def delete_observation(self, _obs) -> None:
            raise AssertionError("delete_observation should not be called without a base observation")

        def create_observation(self, **kwargs):
            return SimpleNamespace(
                id=kwargs["observation_id"],
                generation=kwargs["generation"],
                content=kwargs["content"],
                token_count=kwargs["token_count"],
                trigger_token_count=kwargs["trigger_token_count"],
                observed_up_to_message_id=kwargs["observed_up_to_message_id"],
                current_task=kwargs["current_task"],
                suggested_response=kwargs["suggested_response"],
                timestamp=kwargs["timestamp"],
            )

        def commit(self) -> None:
            return None

    svc = ObservationMemoryService(FakeRepo())
    chunk = BufferedObservationChunk(
        content="first observation",
        token_count=4,
        observed_up_to_message_id="msg-1",
        observed_up_to_timestamp="2026-02-20T10:00:00+00:00",
    )

    activated = svc.activate_buffered_observations(
        chat_id="chat-1",
        base_observation=None,
        chunks=[chunk],
    )

    assert activated is not None
    assert activated.generation == 0
    assert activated.trigger_token_count is None


def test_activate_buffered_observations_increments_generation() -> None:
    deleted_ids: list[str] = []

    class FakeRepo:
        def delete_observation(self, obs) -> None:
            deleted_ids.append(obs.id)

        def create_observation(self, **kwargs):
            return SimpleNamespace(
                id=kwargs["observation_id"],
                generation=kwargs["generation"],
                content=kwargs["content"],
                token_count=kwargs["token_count"],
                trigger_token_count=kwargs["trigger_token_count"],
                observed_up_to_message_id=kwargs["observed_up_to_message_id"],
                current_task=kwargs["current_task"],
                suggested_response=kwargs["suggested_response"],
                timestamp=kwargs["timestamp"],
            )

        def commit(self) -> None:
            return None

    svc = ObservationMemoryService(FakeRepo())
    base_observation = SimpleNamespace(
        id="obs-base",
        generation=1,
        content="existing observation",
        observed_up_to_message_id="msg-9",
        timestamp="2026-02-20T10:01:00+00:00",
        current_task="keep going",
        suggested_response=None,
    )
    chunk = BufferedObservationChunk(
        content="next observation",
        token_count=4,
        observed_up_to_message_id="msg-10",
        observed_up_to_timestamp="2026-02-20T10:02:00+00:00",
    )

    activated = svc.activate_buffered_observations(
        chat_id="chat-1",
        base_observation=cast(Observation, base_observation),
        chunks=[chunk],
    )

    assert activated is not None
    assert activated.generation == 2
    assert deleted_ids == []


def test_activate_buffered_observations_uses_explicit_trigger_token_count() -> None:
    class FakeRepo:
        def get_latest_observation(self, _chat_id: str):
            return None

        def delete_observation(self, _obs) -> None:
            raise AssertionError("delete_observation should not be called without a base observation")

        def create_observation(self, **kwargs):
            return SimpleNamespace(
                id=kwargs["observation_id"],
                generation=kwargs["generation"],
                content=kwargs["content"],
                token_count=kwargs["token_count"],
                trigger_token_count=kwargs["trigger_token_count"],
                observed_up_to_message_id=kwargs["observed_up_to_message_id"],
                current_task=kwargs["current_task"],
                suggested_response=kwargs["suggested_response"],
                timestamp=kwargs["timestamp"],
            )

        def commit(self) -> None:
            return None

    svc = ObservationMemoryService(FakeRepo())
    chunk = BufferedObservationChunk(
        content="triggered summary",
        token_count=4,
        observed_up_to_message_id="msg-1",
        observed_up_to_timestamp="2026-02-20T10:00:00+00:00",
    )

    activated = svc.activate_buffered_observations(
        chat_id="chat-1",
        base_observation=None,
        chunks=[chunk],
        trigger_token_count=1234,
    )

    assert activated is not None
    assert activated.trigger_token_count == 1234
