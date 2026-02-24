import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.db.base import Base
from app.db.models.chat import Chat
from app.db.models.checkpoint import Checkpoint
from app.db.models.message import Message
from app.db.models.project import Project
from app.db.seed import seed_app_data
from app.db.session import get_engine, reset_sessionmaker
from app.main import create_app
from app.mcp.client_manager import reset_mcp_client_manager
from app.tools.registry import reset_tool_registry


def _seed_test_project_and_chat(session) -> None:
    """Create a minimal project and chat for integration tests that expect chat-1."""
    from app.utils.time import utc_now_iso

    now = utc_now_iso()
    if session.get(Project, "proj-1") is None:
        session.add(
            Project(
                id="proj-1",
                name="test-project",
                path="/tmp/test-project",
                last_active=now,
                sort_order=0,
            )
        )
    if session.get(Chat, "chat-1") is None:
        session.add(
            Chat(
                id="chat-1",
                project_id="proj-1",
                title="Test chat",
                created_at=now,
                updated_at=now,
                sort_order=0,
                is_pinned=0,
            )
        )
    if session.get(Message, "msg-1") is None:
        session.add(
            Message(
                id="msg-1",
                chat_id="chat-1",
                role="user",
                content="Test",
                timestamp=now,
                checkpoint_id=None,
            )
        )
    if session.get(Checkpoint, "cp-1") is None:
        session.add(
            Checkpoint(
                id="cp-1",
                chat_id="chat-1",
                message_id="msg-1",
                label="Test",
                timestamp=now,
            )
        )


@pytest.fixture(scope="session", autouse=True)
def test_env() -> None:
    os.environ["DATABASE_URL"] = "sqlite:///./test_agentic.db"
    get_settings.cache_clear()
    reset_sessionmaker()
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        from sqlalchemy.orm import Session

        session = Session(bind=conn)
        seed_app_data(session)
        _seed_test_project_and_chat(session)
        session.commit()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    with TestClient(app) as test_client:
        reset_mcp_client_manager()
        reset_tool_registry()
        yield test_client
