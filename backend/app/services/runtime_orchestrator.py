"""RuntimeOrchestrator: runs AgentLoop + post-agent verification for a single turn."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.config.settings import get_settings
from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.schemas.chat import CheckpointOut, MessageOut
from app.services.agent_loop import AgentLoop
from app.services.api_key_resolver import APIKeyResolver
from app.services.approval_service import ApprovalService
from app.services.post_agent_verifier import (
    format_message_for_agent,
    is_verification_message,
    run_verification,
)
from app.services.settings_service import SettingsService
from app.tools.openrouter_format import get_openrouter_tools
from app.utils.ids import generate_id
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)


@dataclass
class FollowUpTurn:
    """Returned when a verification pass found issues and a follow-up turn is needed."""

    checkpoint_id: str
    content: str


async def run_agent_turn(
    *,
    chat_id: str,
    checkpoint_id: str,
    content: str,
    session_factory,
    event_bus,
) -> FollowUpTurn | None:
    """
    Run a full agent turn: AgentLoop + post-agent verification.

    Creates its own DB session so it can run as a background task.
    Publishes SSE events for messages, checkpoints, verification issues, and errors.

    Returns a FollowUpTurn if verification issues were found and another turn is needed,
    otherwise returns None.
    """
    app_settings = get_settings()
    max_iterations = app_settings.max_agent_iterations

    with session_factory() as session:
        settings_repo = SettingsRepository(session)
        settings_svc = SettingsService(session)
        default_prompt = settings_svc.get_system_prompt()

        loop = AgentLoop(
            chat_repo=ChatRepository(session),
            project_repo=ProjectRepository(session),
            settings_repo=settings_repo,
            settings_service=settings_svc,
            api_key_resolver=APIKeyResolver(settings_repo),
            approval_svc=ApprovalService(session, event_bus=event_bus),
            event_bus=event_bus,
            get_openrouter_tools=get_openrouter_tools,
            default_system_prompt=default_prompt,
            session_factory=session_factory,
        )
        await loop.run(
            chat_id=chat_id,
            checkpoint_id=checkpoint_id,
            content=content,
            max_iterations=max_iterations,
        )

        # Post-agent verification: run checks on files edited this turn
        if not is_verification_message(content):
            chat_repo = ChatRepository(session)
            project_repo = ProjectRepository(session)
            chat_model = chat_repo.get_chat(chat_id)
            if chat_model:
                project = project_repo.get_project(chat_model.project_id)
                project_path = project.path if project else None
                if project_path:
                    edits = chat_repo.list_file_edits_for_checkpoint(chat_id, checkpoint_id)
                    if edits:
                        edited_paths = list(
                            {str(Path(e.file_path).resolve()) for e in edits}
                        )
                        issues, summary, by_tool = await run_verification(
                            edited_paths, project_path
                        )
                        if issues:
                            follow_up = await _persist_verification_issues(
                                chat_id=chat_id,
                                checkpoint_id=checkpoint_id,
                                issues=issues,
                                summary=summary,
                                by_tool=by_tool,
                                chat_model=chat_model,
                                chat_repo=chat_repo,
                                event_bus=event_bus,
                            )
                            return follow_up

    return None

    # agent_done already published by AgentLoop


async def _persist_verification_issues(
    *,
    chat_id: str,
    checkpoint_id: str,
    issues,
    summary: str,
    by_tool: dict,
    chat_model,
    chat_repo: ChatRepository,
    event_bus,
) -> FollowUpTurn:
    """Persist verification issues as a new message/checkpoint and publish SSE events."""
    verification_content = format_message_for_agent(issues)
    ts = utc_now_iso()

    fix_msg = chat_repo.create_message(
        message_id=generate_id("msg"),
        chat_id=chat_id,
        role="user",
        content=verification_content,
        timestamp=ts,
        checkpoint_id=None,
    )
    fix_cp = chat_repo.create_checkpoint(
        checkpoint_id=generate_id("cp"),
        chat_id=chat_id,
        message_id=fix_msg.id,
        label="Verification issues found",
        timestamp=ts,
    )
    chat_repo.link_message_checkpoint(fix_msg, fix_cp.id)
    chat_repo.update_chat_timestamp(chat_model, ts)
    chat_repo.commit()

    msg_out = MessageOut(
        id=fix_msg.id,
        role="user",
        content=fix_msg.content,
        timestamp=fix_msg.timestamp,
        checkpointId=fix_cp.id,
    )
    cp_out = CheckpointOut(
        id=fix_cp.id,
        messageId=fix_cp.message_id,
        timestamp=fix_cp.timestamp,
        label=fix_cp.label,
        fileEdits=[],
        toolCalls=[],
        reasoningBlocks=[],
    )

    await event_bus.publish(
        chat_id,
        {"type": "checkpoint", "payload": {"checkpoint": cp_out.model_dump()}},
    )
    await event_bus.publish(
        chat_id,
        {"type": "message", "payload": {"message": msg_out.model_dump()}},
    )
    await event_bus.publish(
        chat_id,
        {
            "type": "verification_issues",
            "payload": {
                "checkpointId": checkpoint_id,
                "summary": summary,
                "issueCount": len(issues),
                "fileCount": len({i.file for i in issues}),
                "byTool": by_tool,
            },
        },
    )

    return FollowUpTurn(checkpoint_id=fix_cp.id, content=verification_content)
