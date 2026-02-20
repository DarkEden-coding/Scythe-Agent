from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.envelope import err, ok
from app.middleware.error_handler import full_error_message
from app.tools.registry import get_tool_registry

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
def list_tools():
    try:
        registry = get_tool_registry()
        items = []
        for entry in registry.list_entries():
            tool = registry.get_tool(entry.name)
            if tool is None:
                continue
            items.append(
                {
                    "name": entry.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                    "source": entry.source,
                    "kind": entry.kind,
                }
            )
        return ok({"tools": items})
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())
