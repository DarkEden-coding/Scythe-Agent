from app.capabilities.context_budget.manager import _stable_compaction_split_index


def test_stable_compaction_split_index_moves_before_leading_tool_outputs() -> None:
    messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u1"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_1", "function": {"name": "read_file"}}],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "result 1"},
        {"role": "tool", "tool_call_id": "call_2", "content": "result 2"},
        {"role": "assistant", "content": "done"},
    ]

    split_idx = _stable_compaction_split_index(messages, recent_count=4)

    assert split_idx == 2
