from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models.auto_approve_rule import AutoApproveRule
from app.db.models.chat import Chat
from app.db.models.checkpoint import Checkpoint
from app.db.models.context_item import ContextItem
from app.db.models.file_edit import FileEdit
from app.db.models.mcp_server import MCPServer
from app.db.models.mcp_tool_cache import MCPToolCache
from app.db.models.message import Message
from app.db.models.project import Project
from app.db.models.provider_model_cache import ProviderModelCache
from app.db.models.reasoning_block import ReasoningBlock
from app.db.models.settings import Settings
from app.db.models.tool_call import ToolCall


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_demo_data(db: Session) -> None:
    settings = get_settings()
    now = _now()

    if db.get(Settings, 1) is None:
        db.add(
            Settings(
                id=1,
                active_model=settings.default_active_model,
                context_limit=settings.default_context_limit,
                updated_at=now,
            )
        )

    if db.get(Project, "proj-1") is None:
        db.add(
            Project(
                id="proj-1",
                name="dashboard-app",
                path="/Users/darkeden/projects/dashboard-app",
                last_active=now,
                sort_order=0,
            )
        )

    if db.get(Chat, "chat-1") is None:
        db.add(
            Chat(
                id="chat-1",
                project_id="proj-1",
                title="Add dark mode support",
                created_at=now,
                updated_at=now,
                sort_order=0,
                is_pinned=0,
            )
        )

    if db.get(Message, "msg-1") is None:
        db.add_all(
            [
                Message(
                    id="msg-1",
                    chat_id="chat-1",
                    role="user",
                    content="Please add dark mode to the dashboard.",
                    timestamp=now,
                    checkpoint_id="cp-1",
                ),
                Message(
                    id="msg-2",
                    chat_id="chat-1",
                    role="assistant",
                    content="I will update theme tokens and sidebar styles.",
                    timestamp=now,
                    checkpoint_id=None,
                ),
            ]
        )

    if db.get(Checkpoint, "cp-1") is None:
        db.add(
            Checkpoint(
                id="cp-1",
                chat_id="chat-1",
                message_id="msg-1",
                label="User request: dark mode",
                timestamp=now,
            )
        )

    if db.get(ToolCall, "tc-1") is None:
        db.add(
            ToolCall(
                id="tc-1",
                chat_id="chat-1",
                checkpoint_id="cp-1",
                name="edit_file",
                status="completed",
                input_json=json.dumps({"path": "src/components/Dashboard.tsx"}),
                output_text="Edit applied successfully",
                timestamp=now,
                duration_ms=142,
                parallel=0,
                parallel_group=None,
            )
        )

    if db.get(FileEdit, "fe-1") is None:
        db.add(
            FileEdit(
                id="fe-1",
                chat_id="chat-1",
                checkpoint_id="cp-1",
                file_path="src/components/Dashboard.tsx",
                action="modified",
                diff="@@ -1,3 +1,4 @@\n+const dark = true",
                timestamp=now,
            )
        )

    if db.get(ReasoningBlock, "rb-1") is None:
        db.add(
            ReasoningBlock(
                id="rb-1",
                chat_id="chat-1",
                checkpoint_id="cp-1",
                content="Plan edits before running build checks.",
                timestamp=now,
                duration_ms=3200,
            )
        )

    if db.get(ContextItem, "ctx-1") is None:
        db.add_all(
            [
                ContextItem(id="ctx-1", chat_id="chat-1", type="conversation", label="Recent turns", tokens=512),
                ContextItem(id="ctx-2", chat_id="chat-1", type="file", label="src/components/Dashboard.tsx", tokens=260),
            ]
        )

    existing_models = {m.id for m in db.query(ProviderModelCache).all()}
    for idx, model in enumerate(settings.fallback_models):
        key = f"openrouter::{model}"
        if key not in existing_models:
            db.add(
                ProviderModelCache(
                    id=key,
                    provider="openrouter",
                    label=model,
                    context_limit=settings.default_context_limit,
                    raw_json=json.dumps({"id": model, "provider": "openrouter"}),
                    fetched_at=now,
                )
            )

    if db.get(AutoApproveRule, "aar-1") is None:
        db.add(
            AutoApproveRule(
                id="aar-1",
                field="tool",
                value="read_file",
                enabled=1,
                created_at=now,
            )
        )

    if db.get(MCPServer, "mcp-local-1") is None:
        db.add(
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

    if db.get(MCPToolCache, "mcpt-mcp-local-1-echo_tool") is None:
        db.add(
            MCPToolCache(
                id="mcpt-mcp-local-1-echo_tool",
                server_id="mcp-local-1",
                tool_name="echo_tool",
                schema_json=json.dumps(
                    {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                    }
                ),
                description="Echo payload via MCP mock transport",
                discovered_at=now,
            )
        )
