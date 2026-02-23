"""RuntimeOrchestrator: runs AgentLoop + post-agent verification for a single turn."""

from __future__ import annotations

import logging
import json
import re
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
from app.services.plan_service import PlanService
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


def _normalize_heading_label(label: str) -> str:
    return re.sub(r"^#{1,6}\s*", "", label.strip()).strip().lower()


def _replace_markdown_section(markdown: str, heading: str, body: str) -> str:
    lines = markdown.splitlines()
    target = _normalize_heading_label(heading)
    if not target:
        return markdown

    start_idx: int | None = None
    start_level = 0
    for idx, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if not match:
            continue
        level = len(match.group(1))
        title = _normalize_heading_label(match.group(2))
        if title == target:
            start_idx = idx
            start_level = level
            break

    section_lines = [body.rstrip()] if body.strip() else []
    if start_idx is None:
        suffix = f"\n\n## {heading.strip()}\n"
        suffix += section_lines[0] + "\n" if section_lines else "\n"
        return markdown.rstrip() + suffix

    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+(.*)$", lines[idx].strip())
        if not match:
            continue
        if len(match.group(1)) <= start_level:
            end_idx = idx
            break

    heading_line = lines[start_idx]
    replacement = [heading_line, ""]
    if section_lines:
        replacement.extend(section_lines[0].splitlines())
    updated = lines[:start_idx] + replacement + lines[end_idx:]
    return "\n".join(updated).rstrip() + "\n"


def _extract_patch_ops(model_output: str) -> list[dict] | None:
    text = model_output.strip()
    if not text:
        return None

    payload: dict | None = None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            payload = parsed
    except json.JSONDecodeError:
        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text, re.IGNORECASE)
        if fenced:
            try:
                parsed = json.loads(fenced.group(1))
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = None
    if payload is None:
        return None
    ops = payload.get("ops")
    if not isinstance(ops, list):
        return None
    return [op for op in ops if isinstance(op, dict)]


def _apply_plan_edit_output(current_markdown: str, model_output: str) -> str:
    ops = _extract_patch_ops(model_output)
    if ops is None:
        candidate = model_output.strip()
        return candidate if candidate else current_markdown

    updated = current_markdown
    for op in ops:
        op_name = str(op.get("op", "")).strip()
        if op_name == "replace_all":
            content = op.get("content")
            if isinstance(content, str) and content.strip():
                updated = content.strip() + "\n"
            continue
        if op_name == "replace_section":
            heading = op.get("heading")
            content = op.get("content")
            if isinstance(heading, str) and isinstance(content, str):
                updated = _replace_markdown_section(updated, heading, content)
            continue
        if op_name == "append_section":
            heading = op.get("heading")
            content = op.get("content")
            if isinstance(heading, str) and isinstance(content, str):
                tail = f"\n\n## {heading.strip()}\n{content.strip()}\n"
                updated = updated.rstrip() + tail
            continue
    return updated


async def run_agent_turn(
    *,
    chat_id: str,
    checkpoint_id: str,
    content: str,
    session_factory,
    event_bus,
    mode: str = "default",
    active_plan_id: str | None = None,
) -> FollowUpTurn | None:
    """
    Run a full agent turn: AgentLoop + post-agent verification.

    Creates its own DB session so it can run as a background task.
    Publishes SSE events for messages, checkpoints, verification issues, and errors.

    Returns a FollowUpTurn if verification issues were found and another turn is needed,
    otherwise returns None.
    """
    run_mode = mode if mode in {"default", "planning", "plan_edit"} else "default"
    app_settings = get_settings()
    max_iterations = app_settings.max_agent_iterations

    with session_factory() as session:
        settings_repo = SettingsRepository(session)
        settings_svc = SettingsService(session)
        chat_repo = ChatRepository(session)
        default_prompt = settings_svc.get_system_prompt()
        plan_svc = PlanService(session, event_bus=event_bus)

        extra_messages: list[dict] = []
        if run_mode == "planning":
            await event_bus.publish(
                chat_id,
                {
                    "type": "plan_started",
                    "payload": {
                        "checkpointId": checkpoint_id,
                    },
                },
            )
        if run_mode == "plan_edit":
            if not active_plan_id:
                raise ValueError("activePlanId is required for plan_edit mode")
            await plan_svc.sync_external_if_needed(chat_id, active_plan_id)
            existing_plan = await plan_svc.get_plan(chat_id, active_plan_id, include_content=True)
            existing_content = existing_plan.content or ""
            extra_messages.append(
                {
                    "role": "system",
                    "content": (
                        "You are editing an existing markdown implementation plan. "
                        "Return either updated markdown directly, or JSON object: "
                        '{"ops":[{"op":"replace_section","heading":"...","content":"..."}]}.'
                    ),
                }
            )
            extra_messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Current plan markdown:\n\n{existing_content}\n\n"
                        f"Edit request:\n{content}"
                    ),
                }
            )

        loop = AgentLoop(
            chat_repo=chat_repo,
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
        run_result = await loop.run(
            chat_id=chat_id,
            checkpoint_id=checkpoint_id,
            content=content,
            max_iterations=max_iterations,
            mode=run_mode,
            extra_messages=extra_messages or None,
        )

        if run_mode == "planning":
            if not run_result.completed:
                logger.warning(
                    "Planning mode did not complete; skipping plan persistence chat_id=%s checkpoint_id=%s",
                    chat_id,
                    checkpoint_id,
                )
                return None
            plan_markdown = run_result.final_assistant_text.strip()
            if plan_markdown:
                await plan_svc.create_plan(
                    chat_id=chat_id,
                    checkpoint_id=checkpoint_id,
                    content=plan_markdown,
                    title="Implementation Plan",
                    status="ready",
                    last_editor="agent",
                )
            else:
                logger.warning(
                    "Planning mode finished without assistant markdown chat_id=%s checkpoint_id=%s",
                    chat_id,
                    checkpoint_id,
                )
            return None

        if run_mode == "plan_edit":
            if not active_plan_id:
                raise ValueError("activePlanId is required for plan_edit mode")
            if not run_result.completed:
                logger.warning(
                    "Plan edit mode did not complete; skipping plan update chat_id=%s checkpoint_id=%s plan_id=%s",
                    chat_id,
                    checkpoint_id,
                    active_plan_id,
                )
                return None
            current_plan = await plan_svc.get_plan(chat_id, active_plan_id, include_content=True)
            current_md = current_plan.content or ""
            next_md = _apply_plan_edit_output(current_md, run_result.final_assistant_text)
            update_result = await plan_svc.update_plan(
                chat_id=chat_id,
                plan_id=active_plan_id,
                content=next_md,
                base_revision=current_plan.revision,
                last_editor="agent",
                checkpoint_id=checkpoint_id,
            )
            if update_result.conflict:
                await event_bus.publish(
                    chat_id,
                    {
                        "type": "plan_conflict",
                        "payload": {"plan": update_result.plan.model_dump(), "reason": "stale_revision"},
                    },
                )
            return None

        # Post-agent verification: run checks on files edited this turn
        if not is_verification_message(content):
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
