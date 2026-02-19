from unittest.mock import patch

import pytest

from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.db.session import get_sessionmaker
from app.services.api_key_resolver import APIKeyResolver


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


def test_api_key_resolver_db_first_env_fallback() -> None:
    """APIKeyResolver uses DB first, then env fallback."""
    session_factory = get_sessionmaker()
    with session_factory() as db:
        repo = SettingsRepository(db)
        resolver = APIKeyResolver(repo)
        has_key, masked = resolver.resolve_masked()
        assert isinstance(has_key, bool)
        assert isinstance(masked, str)
        if has_key:
            assert len(masked) > 0
        client = resolver.create_client()
        if has_key:
            assert client is not None
        else:
            assert client is None


def test_api_key_resolver_resolve_or_raise_when_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """resolve_or_raise raises ValueError when no key (DB empty, env unset)."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with get_sessionmaker()() as db:
        repo = SettingsRepository(db)
        with patch.object(repo, "get_openrouter_api_key", return_value=None):
            resolver = APIKeyResolver(repo)
            with pytest.raises(ValueError, match="No OpenRouter API key"):
                resolver.resolve_or_raise()

