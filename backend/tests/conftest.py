import os

import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.db.base import Base
from app.db.seed import seed_demo_data
from app.db.session import get_engine, reset_sessionmaker
from app.main import create_app
from app.mcp.client_manager import reset_mcp_client_manager
from app.tools.registry import reset_tool_registry


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
        seed_demo_data(session)
        session.commit()


@pytest.fixture
def client() -> TestClient:
    reset_mcp_client_manager()
    reset_tool_registry()
    app = create_app()
    return TestClient(app)
