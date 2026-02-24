"""Helpers for normalizing todo payloads from update_todo_list."""

from __future__ import annotations

from typing import Any, cast


def normalize_todo_items(raw_items: object) -> list[dict]:
    """Normalize todo payload items to a stable schema."""
    if not isinstance(raw_items, list):
        return []

    normalized: list[dict] = []
    for i, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        item_dict = cast(dict[str, Any], item)

        content_raw = item_dict.get("content")
        content = str(content_raw) if content_raw is not None else ""
        content = content.strip()
        if not content:
            continue

        status_raw = item_dict.get("status")
        status = str(status_raw) if status_raw is not None else "pending"
        status = status.lower()
        if status not in ("pending", "in_progress", "completed"):
            status = "pending"

        sort_order_raw = item_dict.get("sort_order")
        try:
            sort_order = int(sort_order_raw) if sort_order_raw is not None else i
        except (TypeError, ValueError):
            sort_order = i

        normalized.append(
            {
                "content": content,
                "status": status,
                "sort_order": sort_order,
            }
        )
    return normalized
