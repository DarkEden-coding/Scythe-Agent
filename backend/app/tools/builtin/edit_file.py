from __future__ import annotations

from pathlib import Path

from app.tools.contracts import ToolFileEdit, ToolResult


class EditFileTool:
    name = "edit_file"
    description = "Write content to a file."
    input_schema = {
        "type": "object",
        "required": ["path", "content"],
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
    }

    async def run(self, payload: dict) -> ToolResult:
        target = Path(payload.get("path", ""))
        content = str(payload.get("content", ""))
        action = "created"
        previous = None
        if target.exists():
            action = "modified"
            previous = target.read_text(encoding="utf-8")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        diff = None
        if previous is not None and previous != content:
            diff = f"- {previous[:120]}\n+ {content[:120]}"
        file_edit = ToolFileEdit(file_path=str(target), action=action, diff=diff)
        return ToolResult(output=f"{action} {target}", file_edits=[file_edit])

