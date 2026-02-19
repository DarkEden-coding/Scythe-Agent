"""Shared message dict utilities."""

from __future__ import annotations


def strip_message_metadata(messages: list[dict]) -> list[dict]:
    """Remove internal _message_id keys from message dicts before sending to LLM."""
    result = []
    for msg in messages:
        if "_message_id" in msg:
            msg = {k: v for k, v in msg.items() if k != "_message_id"}
        result.append(msg)
    return result
