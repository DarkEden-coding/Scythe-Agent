from app.services.agent_loop import AgentLoop


def _build_loop() -> AgentLoop:
    return AgentLoop(
        chat_repo=None,
        project_repo=None,
        settings_repo=None,
        settings_service=None,
        api_key_resolver=None,
        approval_svc=None,
        event_bus=None,
        get_openrouter_tools=lambda: [],
        default_system_prompt="",
    )


def test_loop_guard_signature_read_file_uses_only_path() -> None:
    loop = _build_loop()
    first = {
        "function": {
            "name": "read_file",
            "arguments": '{"path":"/tmp/x","start":1,"end":300}',
        }
    }
    second = {
        "function": {
            "name": "read_file",
            "arguments": '{"path":"/tmp/x","start":301,"end":600}',
        }
    }
    assert loop._loop_guard_signature(first) == ("read_file", "path=/tmp/x")
    assert loop._loop_guard_signature(first) == loop._loop_guard_signature(second)


def test_loop_guard_signature_ignores_non_file_tools() -> None:
    loop = _build_loop()
    tool_call = {
        "function": {
            "name": "update_todo_list",
            "arguments": '{"todos":[{"content":"a","status":"pending"}]}',
        }
    }
    assert loop._loop_guard_signature(tool_call) is None


def test_loop_guard_signature_list_files_requires_same_path_and_mode() -> None:
    loop = _build_loop()
    recursive = {
        "function": {
            "name": "list_files",
            "arguments": '{"path":"/tmp/dir","recursive":true}',
        }
    }
    non_recursive = {
        "function": {
            "name": "list_files",
            "arguments": '{"path":"/tmp/dir","recursive":false}',
        }
    }
    assert loop._loop_guard_signature(recursive) == (
        "list_files",
        "path=/tmp/dir|recursive=True",
    )
    assert loop._loop_guard_signature(non_recursive) == (
        "list_files",
        "path=/tmp/dir|recursive=False",
    )
