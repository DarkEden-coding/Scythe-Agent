"""Static file checker tool — run verification checks on edited or specified files."""

from __future__ import annotations

from pathlib import Path

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.types import ToolExecutionResult
from app.services.post_agent_verifier import format_message_for_agent, run_verification
from app.tools.path_utils import resolve_path


def _collect_paths_from_checkpoint(context: ToolExecutionContext) -> list[str]:
    chat_repo = context.chat_repo
    chat_id = context.chat_id
    checkpoint_id = context.checkpoint_id
    if chat_repo is not None and checkpoint_id is None and context.tool_call_id:
        try:
            tool_call = chat_repo.get_tool_call(context.tool_call_id)
        except Exception:
            tool_call = None
        if tool_call is not None:
            checkpoint_id = tool_call.checkpoint_id
    if chat_repo is None or not chat_id or not checkpoint_id:
        return []
    try:
        edits = chat_repo.list_file_edits_for_checkpoint(chat_id, checkpoint_id)
    except Exception:
        return []
    deduped: set[str] = set()
    for edit in edits:
        try:
            deduped.add(str(Path(edit.file_path).resolve()))
        except Exception:
            continue
    return sorted(deduped)


def _render_issues(summary: str, by_tool: dict[str, int], issues) -> str:
    by_tool_summary = ", ".join(
        f"{name}={count}" for name, count in sorted(by_tool.items())
    )
    detail = format_message_for_agent(issues)
    if by_tool_summary:
        return f"Static check summary: {summary}\nTools: {by_tool_summary}\n\n{detail}"
    return f"Static check summary: {summary}\n\n{detail}"


async def _handler(payload: dict, context: ToolExecutionContext) -> ToolExecutionResult:
    if not context.project_root:
        return ToolExecutionResult(
            output="No project root available for static checking.",
            file_edits=[],
            ok=False,
        )

    raw_paths = payload.get("paths")
    resolved_paths: list[str] = []
    if isinstance(raw_paths, list):
        for item in raw_paths:
            if not isinstance(item, str) or not item.strip():
                continue
            try:
                p = resolve_path(
                    item,
                    project_root=context.project_root,
                    allow_external=False,
                )
            except ValueError as exc:
                return ToolExecutionResult(output=str(exc), file_edits=[], ok=False)
            resolved_paths.append(str(p))

    if not resolved_paths:
        resolved_paths = _collect_paths_from_checkpoint(context)

    if not resolved_paths:
        return ToolExecutionResult(
            output=(
                "No files to check. Provide paths or run static_file_checker after edits exist "
                "in the current checkpoint."
            ),
            file_edits=[],
            ok=False,
        )

    issues, summary, by_tool = await run_verification(
        resolved_paths, context.project_root
    )
    if not issues:
        return ToolExecutionResult(
            output=f"Static checks passed. {summary}",
            file_edits=[],
            ok=True,
        )

    return ToolExecutionResult(
        output=_render_issues(summary, by_tool, issues),
        file_edits=[],
        ok=True,
    )


TOOL_PLUGIN = ToolPlugin(
    name="static_file_checker",
    description=(
        "Run static verification checks (ruff, ty, py_compile, and tsc filtering to target files). "
        "If paths is omitted, it checks files edited in the current checkpoint so you can iteratively fix issues."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional absolute file paths to check. Defaults to files edited in this checkpoint.",
            }
        },
    },
    approval_policy="rules",
    handler=_handler,
)
