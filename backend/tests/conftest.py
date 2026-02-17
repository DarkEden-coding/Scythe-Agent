import json
import os

import pytest
from fastapi.testclient import TestClient

from app.mcp.client_manager import MCPClientManager
from tests.mocks.mcp_http_transport import MCPHTTPTransport
from tests.mocks.mcp_sse_transport import MCPSSETransport
from tests.mocks.mcp_stdio_transport import MCPStdioTransport

# Register mock MCP transports for tests (production has none)
MCPClientManager.register_transport_factory("stdio", MCPStdioTransport)
MCPClientManager.register_transport_factory("sse", MCPSSETransport)
MCPClientManager.register_transport_factory("http", MCPHTTPTransport)

from app.config.settings import get_settings
from app.db.base import Base
from app.db.models.mcp_server import MCPServer
from app.db.seed import seed_demo_data
from app.db.session import get_engine, reset_sessionmaker
from app.main import create_app
from app.mcp.client_manager import reset_mcp_client_manager
from app.tools.registry import reset_tool_registry


def _seed_mock_mcp_for_tests(session) -> None:
    """Add mock MCP server for phase7 integration tests only."""
    if session.get(MCPServer, "mcp-local-1") is None:
        session.add(
            MCPServer(
                id="mcp-local-1",
                name="local-mock-server",
                transport="stdio",
                config_json=json.dumps(
                    {
                        "mock_tools": [
                            {
                                "name": "echo_tool",
                                "description": "Echo payload via MCP mock transport",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"text": {"type": "string"}},
                                },
                            }
                        ]
                    }
                ),
                enabled=1,
                last_connected_at=None,
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
        seed_demo_data(session)
        _seed_mock_mcp_for_tests(session)
        session.commit()


@pytest.fixture
def client() -> TestClient:
    reset_mcp_client_manager()
    reset_tool_registry()
    app = create_app()
    return TestClient(app)
