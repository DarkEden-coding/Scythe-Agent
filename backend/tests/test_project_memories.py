from pathlib import Path

from app.initial_information.project_memory_titles import add_project_memory_titles


def test_project_memory_api_roundtrip(client) -> None:
    created_project = client.post(
        "/api/projects",
        json={"name": "tmp-project-memory", "path": str(Path.cwd())},
    )
    assert created_project.status_code == 200
    project_id = created_project.json()["data"]["project"]["id"]

    upsert = client.post(
        f"/api/projects/{project_id}/memories",
        json={"title": "Formatting preference", "contentMarkdown": "Prefer concise answers and bullets."},
    )
    assert upsert.status_code == 200
    memory = upsert.json()["data"]["memory"]
    assert memory["title"] == "Formatting preference"
    assert memory["contentMarkdown"] == "Prefer concise answers and bullets."

    listed = client.get(f"/api/projects/{project_id}/memories")
    assert listed.status_code == 200
    memories = listed.json()["data"]["memories"]
    assert len(memories) == 1
    assert memories[0]["title"] == "Formatting preference"

    deleted = client.delete(f"/api/projects/{project_id}/memories/Formatting preference")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deletedTitle"] == "Formatting preference"


def test_project_memory_title_injection_appears_in_runtime_messages(client) -> None:
    # open a direct DB session via app sessionmaker import path to seed memory for proj-1/chat-1
    from app.db.session import get_sessionmaker
    from app.services.project_memory_service import ProjectMemoryService

    with get_sessionmaker()() as session:
        ProjectMemoryService(session).upsert_project_memory(
            project_id="proj-1",
            title="Response style",
            content_markdown="User prefers short, direct responses.",
        )

    debug = client.get("/api/chat/chat-1/debug")
    assert debug.status_code == 200
    assembled = debug.json()["data"]["assembledMessages"]
    system_blocks = [m["content"] for m in assembled if m.get("role") == "system"]
    assert any("Project memory titles available for this conversation" in content for content in system_blocks)
    assert any("Response style" in content for content in system_blocks)


def test_project_memory_title_helper_inserts_after_system_message(client) -> None:
    from app.db.session import get_sessionmaker
    from app.services.project_memory_service import ProjectMemoryService

    with get_sessionmaker()() as session:
        ProjectMemoryService(session).upsert_project_memory(
            project_id="proj-1",
            title="Code style",
            content_markdown="Prefer explicit naming over abbreviations.",
        )
        messages = [
            {"role": "system", "content": "base system"},
            {"role": "user", "content": "hello"},
        ]
        out = add_project_memory_titles(messages, project_id="proj-1", db=session)

    assert out[0]["content"] == "base system"
    assert out[1]["role"] == "system"
    assert "Code style" in out[1]["content"]
