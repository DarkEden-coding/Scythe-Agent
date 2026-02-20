from __future__ import annotations

from app.capabilities.tools.interfaces import ToolExecutionContext, ToolPlugin
from app.capabilities.tools.types import ToolExecutionResult
from app.tools.builtin.update_todo_list import UpdateTodoListTool

_tool = UpdateTodoListTool()


async def _handler(payload: dict, context: ToolExecutionContext) -> ToolExecutionResult:
    result = await _tool.run(
        payload,
        project_root=context.project_root,
        chat_id=context.chat_id,
        chat_repo=context.chat_repo,
        checkpoint_id=context.checkpoint_id,
    )
    return ToolExecutionResult(output=result.output, file_edits=result.file_edits, ok=result.ok)


TOOL_PLUGIN = ToolPlugin(
    name=_tool.name,
    description=_tool.description,
    input_schema=_tool.input_schema,
    approval_policy="always",
    handler=_handler,
)
