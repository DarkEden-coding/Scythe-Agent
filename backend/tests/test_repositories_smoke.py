from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.db.session import get_sessionmaker


def test_project_repository_smoke() -> None:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        repo = ProjectRepository(db)
        projects = repo.list_projects()
        assert projects
        chats = repo.list_chats_for_project(projects[0].id)
        assert chats
        assert repo.get_message_count_for_chat(chats[0].id) >= 1


def test_settings_repository_smoke() -> None:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        repo = SettingsRepository(db)
        settings = repo.get_settings()
        assert settings is not None
        assert settings.active_model
        assert repo.list_models()


def test_chat_repository_smoke() -> None:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        repo = ChatRepository(db)
        chat = repo.get_chat("chat-1")
        assert chat is not None
        assert repo.list_messages(chat.id)
        assert repo.list_checkpoints(chat.id)

