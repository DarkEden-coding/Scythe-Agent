from __future__ import annotations

from app.db.repositories.project_memory_repo import ProjectMemoryRepository

MAX_TITLES = 25


def build_project_memory_titles_text(project_id: str | None, *, db) -> str | None:
    if not project_id:
        return None
    repo = ProjectMemoryRepository(db)
    memories = repo.list_project_memories(project_id)
    if not memories:
        return None
    titles = [memory.title for memory in memories[:MAX_TITLES]]
    rendered_titles = "\n".join(f"- {title}" for title in titles)
    return (
        "Project memory titles available for this conversation:\n"
        f"{rendered_titles}\n\n"
        "These memories are for durable user corrections/preferences only. "
        "Do not treat them as project facts by default. If one looks relevant, read it with the memory tool before relying on it. "
        "Do not write project data, code, plans, or retrieved context into memory."
    )


def add_project_memory_titles(
    messages: list[dict],
    *,
    project_id: str | None,
    db,
) -> list[dict]:
    block_text = build_project_memory_titles_text(project_id, db=db)
    if not block_text:
        return list(messages)
    block = {"role": "system", "content": block_text}
    result = list(messages)
    insert_at = 0
    for i, message in enumerate(result):
        if message.get("role") == "system":
            insert_at = i + 1
        else:
            break
    result.insert(insert_at, block)
    return result
