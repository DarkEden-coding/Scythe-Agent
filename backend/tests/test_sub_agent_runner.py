import asyncio
import json
from types import SimpleNamespace

import pytest

import app.services.sub_agent_runner as sub_agent_runner_module
from app.services.sub_agent_runner import SubAgentRunner


class _DummyApiKeyResolver:
    def create_client(self, _provider: str):
        return object()

    def resolve(self, _provider: str):
        return "fake-key"


class _DummySettingsService:
    def get_settings(self):
        return SimpleNamespace(
            model="dummy-model",
            modelProvider="openrouter",
            modelKey=None,
            modelMetadataByKey={},
            modelMetadata={},
            reasoningLevel=None,
        )


class _RecordingEventBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def publish(self, chat_id: str, event: dict) -> None:
        self.events.append((chat_id, event))


class _FailingTool:
    async def run(self, *args, **kwargs):
        raise AssertionError("Sub-agent local todo/submit tools should not hit registry")


class _RecordingRegistry:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_tool(self, name: str):
        self.calls.append(name)
        return _FailingTool()


class _LocalTodoThenSubmitStreamer:
    def __init__(self, _chat_repo, _event_bus) -> None:
        self.step = 0

    async def stream_completion(self, **kwargs):
        self.step += 1
        if self.step == 1:
            args = {
                "todos": [
                    {"content": "Do sub-task", "status": "completed", "sort_order": 0}
                ]
            }
            return SimpleNamespace(
                text="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "function": {
                            "name": "update_todo_list",
                            "arguments": json.dumps(args),
                        },
                    }
                ],
                finish_reason="tool_calls",
                finish_content="",
            )
        if self.step == 2:
            return SimpleNamespace(
                text="Sub-agent finished work.",
                tool_calls=[
                    {
                        "id": "call-2",
                        "function": {"name": "submit_task", "arguments": "{}"},
                    }
                ],
                finish_reason="tool_calls",
                finish_content="",
            )
        raise AssertionError("Unexpected extra iteration")


class _CancelledStreamer:
    def __init__(self, _chat_repo, _event_bus) -> None:
        pass

    async def stream_completion(self, **kwargs):
        raise asyncio.CancelledError()


class _CapturePromptThenSubmitStreamer:
    captured_messages: list[dict] | None = None

    def __init__(self, _chat_repo, _event_bus) -> None:
        pass

    async def stream_completion(self, **kwargs):
        type(self).captured_messages = kwargs.get("messages")
        return SimpleNamespace(
            text="Done.",
            tool_calls=[
                {
                    "id": "call-capture-1",
                    "function": {"name": "submit_task", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
            finish_content="",
        )


class _TextThenToolOnlySubmitStreamer:
    def __init__(self, _chat_repo, _event_bus) -> None:
        self.step = 0

    async def stream_completion(self, **kwargs):
        self.step += 1
        if self.step == 1:
            return SimpleNamespace(
                text="Final sub-agent answer.",
                tool_calls=[
                    {
                        "id": "call-text-1",
                        "function": {"name": "update_todo_list", "arguments": '{"todos":[]}'},
                    }
                ],
                finish_reason="tool_calls",
                finish_content="",
            )
        if self.step == 2:
            return SimpleNamespace(
                text="",
                tool_calls=[
                    {
                        "id": "call-text-2",
                        "function": {"name": "submit_task", "arguments": "{}"},
                    }
                ],
                finish_reason="tool_calls",
                finish_content="",
            )
        raise AssertionError("Unexpected extra iteration")


class _AlwaysEmptyStopStreamer:
    def __init__(self, _chat_repo, _event_bus) -> None:
        pass

    async def stream_completion(self, **kwargs):
        return SimpleNamespace(
            text="",
            tool_calls=[],
            finish_reason="stop",
            finish_content="",
        )


class _TextOnlyStopStreamer:
    def __init__(self, _chat_repo, _event_bus) -> None:
        pass

    async def stream_completion(self, **kwargs):
        return SimpleNamespace(
            text="Partial answer from sub-agent.",
            tool_calls=[],
            finish_reason="stop",
            finish_content="",
        )


class _MaxIterationForcedResponseStreamer:
    calls: list[dict] = []

    def __init__(self, _chat_repo, _event_bus) -> None:
        self.step = 0

    async def stream_completion(self, **kwargs):
        type(self).calls.append(kwargs)
        self.step += 1
        if self.step == 1:
            return SimpleNamespace(
                text="",
                tool_calls=[],
                finish_reason="stop",
                finish_content="",
            )
        if self.step == 2:
            return SimpleNamespace(
                text="Forced final answer from sub-agent.",
                tool_calls=[],
                finish_reason="stop",
                finish_content="",
            )
        raise AssertionError("Unexpected extra iteration")


def _build_runner(event_bus: _RecordingEventBus) -> SubAgentRunner:
    return SubAgentRunner(
        chat_repo=SimpleNamespace(),
        project_repo=SimpleNamespace(),
        settings_repo=SimpleNamespace(),
        settings_service=_DummySettingsService(),
        api_key_resolver=_DummyApiKeyResolver(),
        event_bus=event_bus,
        get_openrouter_tools_fn=lambda exclude_names=None: [],
        default_system_prompt="You are a sub-agent.",
    )


def test_sub_agent_runner_uses_local_todo_list_for_submit(monkeypatch) -> None:
    event_bus = _RecordingEventBus()
    registry = _RecordingRegistry()
    monkeypatch.setattr(sub_agent_runner_module, "LLMStreamer", _LocalTodoThenSubmitStreamer)
    monkeypatch.setattr(sub_agent_runner_module, "get_tool_registry", lambda: registry)

    result = asyncio.run(
        _build_runner(event_bus).run(
            chat_id="chat-1",
            sub_agent_id="sa-test-1",
            tool_call_id="tc-spawn-1",
            task="Complete task",
            context_hint=None,
            project_path=None,
            model="dummy-model",
            model_provider="openrouter",
            max_iterations=4,
        )
    )

    assert result.status == "completed"
    assert registry.calls == []


def test_sub_agent_runner_includes_iteration_budget_guidance(monkeypatch) -> None:
    event_bus = _RecordingEventBus()
    registry = _RecordingRegistry()
    _CapturePromptThenSubmitStreamer.captured_messages = None
    monkeypatch.setattr(
        sub_agent_runner_module, "LLMStreamer", _CapturePromptThenSubmitStreamer
    )
    monkeypatch.setattr(sub_agent_runner_module, "get_tool_registry", lambda: registry)

    result = asyncio.run(
        _build_runner(event_bus).run(
            chat_id="chat-1",
            sub_agent_id="sa-test-iteration-budget",
            tool_call_id="tc-spawn-iteration-budget",
            task="Complete task",
            context_hint=None,
            project_path=None,
            model="dummy-model",
            model_provider="openrouter",
            max_iterations=7,
        )
    )

    assert result.status == "completed"
    messages = _CapturePromptThenSubmitStreamer.captured_messages or []
    system_messages = [m for m in messages if m.get("role") == "system"]
    assert any("hard cap of 7 iterations" in (m.get("content") or "") for m in system_messages)
    assert any(
        "explicitly state which requested items are missing" in (m.get("content") or "")
        for m in system_messages
    )


def test_sub_agent_runner_uses_last_non_empty_text_on_submit(monkeypatch) -> None:
    event_bus = _RecordingEventBus()
    registry = _RecordingRegistry()
    monkeypatch.setattr(
        sub_agent_runner_module, "LLMStreamer", _TextThenToolOnlySubmitStreamer
    )
    monkeypatch.setattr(sub_agent_runner_module, "get_tool_registry", lambda: registry)

    result = asyncio.run(
        _build_runner(event_bus).run(
            chat_id="chat-1",
            sub_agent_id="sa-test-last-text",
            tool_call_id="tc-spawn-last-text",
            task="Complete task",
            context_hint=None,
            project_path=None,
            model="dummy-model",
            model_provider="openrouter",
            max_iterations=4,
        )
    )

    assert result.status == "completed"
    assert result.output_text == "Final sub-agent answer."


def test_sub_agent_runner_publishes_cancelled_end(monkeypatch) -> None:
    event_bus = _RecordingEventBus()
    registry = _RecordingRegistry()
    monkeypatch.setattr(sub_agent_runner_module, "LLMStreamer", _CancelledStreamer)
    monkeypatch.setattr(sub_agent_runner_module, "get_tool_registry", lambda: registry)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            _build_runner(event_bus).run(
                chat_id="chat-1",
                sub_agent_id="sa-test-2",
                tool_call_id="tc-spawn-2",
                task="Any task",
                context_hint=None,
                project_path=None,
                model="dummy-model",
                model_provider="openrouter",
                max_iterations=2,
            )
        )

    end_events = [
        e for _chat_id, e in event_bus.events if e.get("type") == "sub_agent_end"
    ]
    assert end_events
    assert end_events[-1]["payload"]["status"] == "cancelled"


def test_sub_agent_runner_max_iterations_returns_non_empty_output_when_no_text(monkeypatch) -> None:
    event_bus = _RecordingEventBus()
    registry = _RecordingRegistry()
    monkeypatch.setattr(sub_agent_runner_module, "LLMStreamer", _AlwaysEmptyStopStreamer)
    monkeypatch.setattr(sub_agent_runner_module, "get_tool_registry", lambda: registry)

    result = asyncio.run(
        _build_runner(event_bus).run(
            chat_id="chat-1",
            sub_agent_id="sa-test-max-iter-empty",
            tool_call_id="tc-spawn-max-iter-empty",
            task="Any task",
            context_hint=None,
            project_path=None,
            model="dummy-model",
            model_provider="openrouter",
            max_iterations=1,
        )
    )

    assert result.status == "max_iterations"
    assert result.output_text.strip()
    assert "did not gather enough context" in result.output_text


def test_sub_agent_runner_max_iterations_forces_final_response_without_tools(
    monkeypatch,
) -> None:
    event_bus = _RecordingEventBus()
    registry = _RecordingRegistry()
    _MaxIterationForcedResponseStreamer.calls = []
    monkeypatch.setattr(
        sub_agent_runner_module, "LLMStreamer", _MaxIterationForcedResponseStreamer
    )
    monkeypatch.setattr(sub_agent_runner_module, "get_tool_registry", lambda: registry)

    result = asyncio.run(
        _build_runner(event_bus).run(
            chat_id="chat-1",
            sub_agent_id="sa-test-max-iter-text",
            tool_call_id="tc-spawn-max-iter-text",
            task="Any task",
            context_hint=None,
            project_path=None,
            model="dummy-model",
            model_provider="openrouter",
            max_iterations=1,
        )
    )

    assert result.status == "max_iterations"
    assert result.output_text == "Forced final answer from sub-agent."
    assert len(_MaxIterationForcedResponseStreamer.calls) == 2
    forced_call = _MaxIterationForcedResponseStreamer.calls[-1]
    assert forced_call.get("tools") is None
    forced_messages = forced_call.get("messages") or []
    assert forced_messages[-1]["role"] == "user"
    assert "Iteration cap reached. Do not call tools." in forced_messages[-1]["content"]
