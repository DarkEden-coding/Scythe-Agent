import asyncio
import types

from app.services.tool_executor import ToolExecutor


class _DummyChatRepo:
    def __init__(self) -> None:
        self.created_tool_calls = 0
        self.commits = 0

    def create_tool_call(self, **kwargs) -> None:
        self.created_tool_calls += 1

    def commit(self) -> None:
        self.commits += 1


class _DummyApprovalService:
    def should_auto_approve(self, tool_name: str, input_payload: dict) -> bool:
        return True


class _DummyEventBus:
    async def publish(self, chat_id: str, event: dict) -> None:
        return None


def test_execute_tool_calls_parallelism_is_bounded() -> None:
    repo = _DummyChatRepo()
    executor = ToolExecutor(
        repo,
        _DummyApprovalService(),
        _DummyEventBus(),
        max_parallel_tool_calls=4,
    )

    active = 0
    peak = 0

    async def _fake_execute_one(self, *args, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"role": "tool", "tool_call_id": "x", "content": "ok"}

    executor._execute_one = types.MethodType(_fake_execute_one, executor)  # type: ignore[method-assign]

    tool_calls = [
        {"id": f"call-{i}", "function": {"name": "read_file", "arguments": "{}"}}
        for i in range(20)
    ]
    results = asyncio.run(
        executor.execute_tool_calls(
            tool_calls_from_stream=tool_calls,
            chat_id="chat-1",
            checkpoint_id="cp-1",
        )
    )

    assert len(results) == 20
    assert peak <= 4
    assert repo.created_tool_calls == 20
    assert repo.commits == 1
