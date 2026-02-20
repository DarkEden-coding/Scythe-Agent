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


def test_tool_argument_similarity_normalizes_json_key_order() -> None:
    loop = _build_loop()
    left = loop._canonicalize_tool_arguments('{"path":"/tmp/x","recursive":false}')
    right = loop._canonicalize_tool_arguments('{"recursive":false,"path":"/tmp/x"}')
    assert left == right
    assert loop._tool_args_are_similar(left, right)


def test_tool_argument_similarity_accepts_small_argument_variation() -> None:
    loop = _build_loop()
    first = loop._canonicalize_tool_arguments('{"path":"/tmp/x","start":1,"end":300}')
    second = loop._canonicalize_tool_arguments('{"path":"/tmp/x","start":1,"end":320}')
    assert loop._tool_args_are_similar(first, second)
