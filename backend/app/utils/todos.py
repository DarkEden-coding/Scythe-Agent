"""Helpers for normalizing todo payloads from update_todo_list."""

from __future__ import annotations


def normalize_todo_items(raw_items: object) -> list[dict]:
    """Normalize todo payload items to a stable schema."""
    if not isinstance(raw_items, list):
        return []

    normalized: list[dict] = []
    for i, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        status = str(item.get("status", "pending")).lower()
        if status not in ("pending", "in_progress", "completed"):
            status = "pending"
        normalized.append(
            {
                "content": content,
                "status": status,
                "sort_order": int(item.get("sort_order", i)),
            }
        )
    return normalized
