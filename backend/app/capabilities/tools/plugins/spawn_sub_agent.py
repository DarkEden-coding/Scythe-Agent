"""Spawn sub-agent tool — main agent delegates subtasks to parallel sub-agents."""

from __future__ import annotations

import asyncio

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.types import ToolExecutionResult
from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.settings_repo import SettingsRepository
from app.services.api_key_resolver import APIKeyResolver
from app.services.event_bus import get_event_bus
from app.services.settings_service import SettingsService
from app.services.sub_agent_runner import SubAgentRunner
from app.utils.ids import generate_id
from app.utils.time import utc_now_iso


async def _handler(payload: dict, context: ToolExecutionContext) -> ToolExecutionResult:
    """Run a sub-agent with the given task and optional context hint."""
    task = (payload.get("task") or "").strip()
    if not task:
        return ToolExecutionResult(output="Error: task is required.", ok=False)

    context_hint = (payload.get("context_hint") or "").strip() or None
    chat_id = context.chat_id
    chat_repo = context.chat_repo
    project_root = context.project_root
    tool_call_id = context.tool_call_id or ""

    if not chat_id or not chat_repo:
        return ToolExecutionResult(output="Error: chat context required.", ok=False)

    settings_repo = SettingsRepository(chat_repo.db)
    settings_svc = SettingsService(chat_repo.db)
    sub_settings = settings_repo.get_sub_agent_settings()

    sub_model = sub_settings.get("sub_agent_model")
    sub_provider = sub_settings.get("sub_agent_model_provider")
    max_iterations = sub_settings.get("sub_agent_max_iterations") or 25

    if not sub_model:
        main_settings = settings_svc.get_settings()
        sub_model = main_settings.model
        sub_provider = main_settings.modelProvider or settings_repo.get_provider_for_model(
            sub_model
        )

    if not sub_provider:
        sub_provider = "openrouter"

    sub_agent_id = generate_id("sa")
    ts = utc_now_iso()

    chat_repo.create_sub_agent_run(
        sub_agent_id=sub_agent_id,
        chat_id=chat_id,
        tool_call_id=tool_call_id,
        task=task,
        model=sub_model,
        status="running",
        timestamp=ts,
    )
    chat_repo.commit()

    event_bus = get_event_bus()
    await event_bus.publish(
        chat_id,
        {
            "type": "sub_agent_start",
            "payload": {
                "subAgentId": sub_agent_id,
                "task": task,
                "model": sub_model,
                "toolCallId": tool_call_id,
            },
        },
    )

    project_repo = ProjectRepository(chat_repo.db)
    api_key_resolver = APIKeyResolver(settings_repo)
    default_prompt = settings_svc.get_system_prompt()

    runner = SubAgentRunner(
        chat_repo=chat_repo,
        project_repo=project_repo,
        settings_repo=settings_repo,
        settings_service=settings_svc,
        api_key_resolver=api_key_resolver,
        event_bus=event_bus,
        default_system_prompt=default_prompt,
    )

    try:
        result = await runner.run(
            chat_id=chat_id,
            sub_agent_id=sub_agent_id,
            tool_call_id=tool_call_id,
            task=task,
            context_hint=context_hint,
            project_path=project_root,
            model=sub_model,
            model_provider=sub_provider,
            max_iterations=max_iterations,
        )
    except asyncio.CancelledError:
        run_row = chat_repo.get_sub_agent_run(sub_agent_id)
        if run_row:
            chat_repo.set_sub_agent_run_status(
                run_row,
                status="cancelled",
                output_text="Sub-agent cancelled.",
            )
            chat_repo.commit()
        raise

    run_row = chat_repo.get_sub_agent_run(sub_agent_id)
    if run_row:
        chat_repo.set_sub_agent_run_status(
            run_row,
            status=result.status,
            output_text=result.output_text,
            duration_ms=result.duration_ms,
        )
        chat_repo.commit()

    return ToolExecutionResult(
        output=result.output_text,
        ok=result.status == "completed",
    )


TOOL_PLUGIN = ToolPlugin(
    name="spawn_sub_agent",
    description=(
        "Delegate a subtask to a sub-agent that runs its own tool loop. Use for parallel work: "
        "e.g. gathering context from multiple paths, performing migrations across files, or "
        "independent analysis tasks. Each sub-agent has its own iteration limit and cannot spawn "
        "further sub-agents. Spawn multiple sub-agents in one turn for parallel execution."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "What the sub-agent should accomplish"},
            "context_hint": {
                "type": "string",
                "description": "Optional brief context from the parent conversation",
            },
        },
        "required": ["task"],
    },
    approval_policy="always",
    handler=_handler,
)
