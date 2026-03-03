import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.capabilities.tools.interfaces import ToolExecutionContext
from app.capabilities.tools.plugins import static_file_checker as checker_module


class _DummyChatRepo:
    def __init__(
        self, *, edits: list[str], tool_checkpoint_id: str | None = None
    ) -> None:
        self._edits = edits
        self._tool_checkpoint_id = tool_checkpoint_id

    def list_file_edits_for_checkpoint(self, chat_id: str, checkpoint_id: str):
        assert chat_id == "chat-1"
        assert checkpoint_id in {"cp-1", "cp-from-tool"}
        return [SimpleNamespace(file_path=p) for p in self._edits]

    def get_tool_call(self, tool_call_id: str):
        if tool_call_id != "tc-1" or not self._tool_checkpoint_id:
            return None
        return SimpleNamespace(checkpoint_id=self._tool_checkpoint_id)


def _abs_pair() -> tuple[str, str]:
    root = (Path.cwd() / "backend").resolve()
    target = (root / "app" / "main.py").resolve()
    return str(root), str(target)


def test_static_file_checker_uses_explicit_paths(monkeypatch) -> None:
    project_root, target = _abs_pair()
    captured: dict[str, object] = {}

    async def _fake_run_verification(paths: list[str], root: str):
        captured["paths"] = paths
        captured["root"] = root
        return ([], "0 issues in 0 files", {})

    monkeypatch.setattr(checker_module, "run_verification", _fake_run_verification)

    result = asyncio.run(
        checker_module._handler(
            {"paths": [target]},
            ToolExecutionContext(project_root=project_root, chat_id="chat-1"),
        )
    )

    assert result.ok is True
    assert captured["paths"] == [target]
    assert captured["root"] == project_root


def test_static_file_checker_defaults_to_checkpoint_edits(monkeypatch) -> None:
    project_root, target = _abs_pair()
    captured: dict[str, object] = {}

    issue = SimpleNamespace(
        file=target,
        line=10,
        column=1,
        code="F401",
        message="unused import",
        tool="ruff",
    )

    async def _fake_run_verification(paths: list[str], root: str):
        captured["paths"] = paths
        captured["root"] = root
        return ([issue], "1 issue in 1 file", {"ruff": 1})

    monkeypatch.setattr(checker_module, "run_verification", _fake_run_verification)
    monkeypatch.setattr(
        checker_module,
        "format_message_for_agent",
        lambda issues: f"formatted {len(issues)} issue",
    )

    result = asyncio.run(
        checker_module._handler(
            {},
            ToolExecutionContext(
                project_root=project_root,
                chat_id="chat-1",
                checkpoint_id="cp-1",
                chat_repo=_DummyChatRepo(edits=[target]),
            ),
        )
    )

    assert result.ok is True
    assert captured["paths"] == [target]
    assert captured["root"] == project_root
    assert "formatted 1 issue" in result.output
    assert "Tools: ruff=1" in result.output


def test_static_file_checker_uses_tool_call_checkpoint_when_missing(
    monkeypatch,
) -> None:
    project_root, target = _abs_pair()

    async def _fake_run_verification(paths: list[str], root: str):
        return ([], "0 issues in 0 files", {})

    monkeypatch.setattr(checker_module, "run_verification", _fake_run_verification)

    result = asyncio.run(
        checker_module._handler(
            {},
            ToolExecutionContext(
                project_root=project_root,
                chat_id="chat-1",
                checkpoint_id=None,
                tool_call_id="tc-1",
                chat_repo=_DummyChatRepo(
                    edits=[target], tool_checkpoint_id="cp-from-tool"
                ),
            ),
        )
    )

    assert result.ok is True
    assert "Static checks passed" in result.output
