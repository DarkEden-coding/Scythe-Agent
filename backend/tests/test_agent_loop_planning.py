import asyncio
from types import SimpleNamespace

import app.services.agent_loop as agent_loop_module
from app.services.agent_loop import AgentLoop


class _DummyApiKeyResolver:
    def create_client(self, _provider: str):
        return object()

    def resolve(self, _provider: str):
        return "fake-key"


class _DummyProjectRepo:
    def get_project(self, _project_id: str):
        return None


class _DummySettingsRepo:
    def get_provider_for_model(self, _model: str) -> str:
        return "openrouter"

    def get_memory_settings(self) -> dict:
        return {}


class _DummySettingsService:
    def get_settings(self):
        return SimpleNamespace(
            model="dummy-model",
            modelProvider="openrouter",
            modelKey=None,
            modelMetadataByKey={},
            modelMetadata={},
            reasoningLevel=None,
            contextLimit=128_000,
        )


class _RecordingChatRepo:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(id="chat-1", project_id="proj-1")
        self.saved_messages: list[dict] = []
        self.updated_timestamps: list[str] = []

    def get_chat(self, chat_id: str):
        return self.chat if chat_id == "chat-1" else None

    def list_messages(self, _chat_id: str):
        return []

    def create_message(
        self,
        *,
        message_id: str,
        chat_id: str,
        role: str,
        content: str,
        timestamp: str,
        checkpoint_id: str | None,
    ):
        self.saved_messages.append(
            {
                "id": message_id,
                "chat_id": chat_id,
                "role": role,
                "content": content,
                "timestamp": timestamp,
                "checkpoint_id": checkpoint_id,
            }
        )
        return SimpleNamespace(
            id=message_id,
            chat_id=chat_id,
            role=role,
            content=content,
            timestamp=timestamp,
            checkpoint_id=checkpoint_id,
        )

    def update_chat_timestamp(self, _chat, ts: str) -> None:
        self.updated_timestamps.append(ts)

    def commit(self) -> None:
        return None


class _RecordingEventBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def publish(self, chat_id: str, event: dict) -> None:
        self.events.append((chat_id, event))


class _PassthroughContextBudgetManager:
    def __init__(self, _chat_repo, _settings_repo) -> None:
        pass

    async def prepare(
        self,
        *,
        chat_id: str,
        base_messages: list[dict],
        default_system_prompt: str,
        project_path: str | None,
        provider,
        model: str,
        context_limit: int,
    ):
        del chat_id, default_system_prompt, project_path, provider, model, context_limit
        return SimpleNamespace(messages=base_messages)


class _NoopToolExecutor:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def execute_tool_calls(
        self,
        *,
        tool_calls_from_stream: list[dict],
        chat_id: str,
        checkpoint_id: str,
    ) -> list[dict]:
        del tool_calls_from_stream, chat_id, checkpoint_id
        return []


class _ScriptedStreamer:
    scripted_results: list[SimpleNamespace] = []

    def __init__(self, _chat_repo, _event_bus) -> None:
        self._cursor = 0

    async def stream_completion(self, **_kwargs):
        if self._cursor >= len(type(self).scripted_results):
            raise AssertionError("Unexpected extra stream_completion call")
        result = type(self).scripted_results[self._cursor]
        self._cursor += 1
        return result


def _build_loop(chat_repo: _RecordingChatRepo, event_bus: _RecordingEventBus) -> AgentLoop:
    return AgentLoop(
        chat_repo=chat_repo,
        project_repo=_DummyProjectRepo(),
        settings_repo=_DummySettingsRepo(),
        settings_service=_DummySettingsService(),
        api_key_resolver=_DummyApiKeyResolver(),
        approval_svc=SimpleNamespace(),
        event_bus=event_bus,
        get_openrouter_tools=lambda: [],
        default_system_prompt="You are an assistant.",
        session_factory=None,
    )


def test_planning_mode_emits_intermediate_text_but_not_final_plan_message(monkeypatch) -> None:
    _ScriptedStreamer.scripted_results = [
        SimpleNamespace(
            text="I found the subsystem layout.",
            tool_calls=[
                {
                    "id": "call-read-1",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path":"/tmp/test.txt"}',
                    },
                }
            ],
            finish_reason="tool_calls",
            finish_content="",
        ),
        SimpleNamespace(
            text="# Plan\n\n1. Implement the changes.\n2. Run tests.",
            tool_calls=[],
            finish_reason="stop",
            finish_content="",
        ),
    ]
    monkeypatch.setattr(agent_loop_module, "ContextBudgetManager", _PassthroughContextBudgetManager)
    monkeypatch.setattr(agent_loop_module, "LLMStreamer", _ScriptedStreamer)
    monkeypatch.setattr(agent_loop_module, "ToolExecutor", _NoopToolExecutor)

    chat_repo = _RecordingChatRepo()
    event_bus = _RecordingEventBus()
    loop = _build_loop(chat_repo, event_bus)

    result = asyncio.run(
        loop.run(
            chat_id="chat-1",
            checkpoint_id="cp-1",
            content="Plan this change",
            max_iterations=4,
            mode="planning",
        )
    )

    assert result.completed is True
    assert result.final_assistant_text == "# Plan\n\n1. Implement the changes.\n2. Run tests."
    assert [m["content"] for m in chat_repo.saved_messages] == ["I found the subsystem layout."]
    message_events = [event for _chat_id, event in event_bus.events if event.get("type") == "message"]
    assert len(message_events) == 1
    assert (
        message_events[0]["payload"]["message"]["content"]
        == "I found the subsystem layout."
    )


def test_planning_mode_does_not_reuse_intermediate_text_when_terminal_output_is_empty(
    monkeypatch,
) -> None:
    _ScriptedStreamer.scripted_results = [
        SimpleNamespace(
            text="Investigating files now.",
            tool_calls=[
                {
                    "id": "call-read-2",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path":"/tmp/another.txt"}',
                    },
                }
            ],
            finish_reason="tool_calls",
            finish_content="",
        ),
        SimpleNamespace(
            text="",
            tool_calls=[],
            finish_reason="stop",
            finish_content="",
        ),
    ]
    monkeypatch.setattr(agent_loop_module, "ContextBudgetManager", _PassthroughContextBudgetManager)
    monkeypatch.setattr(agent_loop_module, "LLMStreamer", _ScriptedStreamer)
    monkeypatch.setattr(agent_loop_module, "ToolExecutor", _NoopToolExecutor)

    chat_repo = _RecordingChatRepo()
    event_bus = _RecordingEventBus()
    loop = _build_loop(chat_repo, event_bus)

    result = asyncio.run(
        loop.run(
            chat_id="chat-1",
            checkpoint_id="cp-2",
            content="Plan this change",
            max_iterations=4,
            mode="planning",
        )
    )

    assert result.completed is True
    assert result.final_assistant_text == ""
    assert [m["content"] for m in chat_repo.saved_messages] == ["Investigating files now."]
