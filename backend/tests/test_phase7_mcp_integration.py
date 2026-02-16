import asyncio
import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.db.models.mcp_server import MCPServer
from app.db.models.mcp_tool_cache import MCPToolCache
from app.db.repositories.chat_repo import ChatRepository
from app.db.session import get_sessionmaker
from app.main import create_app
from app.mcp.client_manager import MCPClientManager, reset_mcp_client_manager
from app.tools.registry import get_tool_registry, reset_tool_registry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_mcp_discovery_cache_success_and_partial_failure() -> None:
    with get_sessionmaker()() as session:
        if session.get(MCPServer, "mcp-fail-1") is None:
            session.add(
                MCPServer(
                    id="mcp-fail-1",
                    name="failing-server",
                    transport="invalid",
                    config_json=json.dumps({}),
                    enabled=1,
                    last_connected_at=None,
                )
            )
        if session.get(MCPToolCache, "mcpt-mcp-fail-1-cached_tool") is None:
            session.add(
                MCPToolCache(
                    id="mcpt-mcp-fail-1-cached_tool",
                    server_id="mcp-fail-1",
                    tool_name="cached_tool",
                    schema_json=json.dumps({"type": "object"}),
                    description="stale cached tool",
                    discovered_at=_now(),
                )
            )
        session.commit()

        manager = MCPClientManager()
        discovered, errors = asyncio.run(manager.discover_and_cache_tools(session))

        names = {(d.server_id, d.name) for d in discovered}
        assert ("mcp-local-1", "echo_tool") in names
        assert ("mcp-fail-1", "cached_tool") in names
        assert any("mcp-fail-1" in err for err in errors)


def test_registry_contains_mcp_tools_after_startup_discovery() -> None:
    reset_mcp_client_manager()
    reset_tool_registry()
    with TestClient(create_app()) as startup_client:
        response = startup_client.get("/api/settings")
        assert response.status_code == 200
    tools = get_tool_registry().list_tools()
    assert "mcp::mcp-local-1::echo_tool" in tools


def test_approved_mcp_tool_call_executes_through_approval_route(client) -> None:
    reset_mcp_client_manager()
    reset_tool_registry()
    with TestClient(create_app()) as startup_client:
        with get_sessionmaker()() as session:
            repo = ChatRepository(session)
            repo.create_tool_call(
                tool_call_id="tc-mcp-approve-1",
                chat_id="chat-1",
                checkpoint_id="cp-1",
                name="mcp::mcp-local-1::echo_tool",
                status="pending",
                input_json=json.dumps({"text": "hello"}),
                timestamp=_now(),
            )
            repo.commit()

        response = startup_client.post("/api/chat/chat-1/approve", json={"toolCallId": "tc-mcp-approve-1"})
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["toolCall"]["id"] == "tc-mcp-approve-1"
        assert payload["toolCall"]["status"] == "completed"
        assert "echo_tool" in (payload["toolCall"]["output"] or "")
