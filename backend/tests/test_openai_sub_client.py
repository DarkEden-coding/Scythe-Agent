from app.providers.openai_sub.client import _messages_to_codex_input


def test_messages_to_codex_input_keeps_matched_tool_output() -> None:
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path":"a.txt"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_123", "content": "hello"},
    ]

    input_items, _ = _messages_to_codex_input(messages)

    assert input_items == [
        {
            "type": "function_call",
            "call_id": "call_123",
            "name": "read_file",
            "arguments": '{"path":"a.txt"}',
        },
        {
            "type": "function_call_output",
            "call_id": "call_123",
            "output": "hello",
        },
    ]


def test_messages_to_codex_input_drops_orphan_tool_output() -> None:
    messages = [
        {"role": "tool", "tool_call_id": "call_orphan", "content": "orphan output"}
    ]

    input_items, _ = _messages_to_codex_input(messages)

    assert input_items == []
