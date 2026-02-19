"""MCP server and tool management API."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_db
from app.api.envelope import err, ok
from app.middleware.error_handler import full_error_message
from app.schemas.mcp import (
    CreateMCPServerRequest,
    MCPServersResponse,
    RefreshMCPResponse,
    SetMCPServerEnabledRequest,
    SetMCPToolEnabledRequest,
    UpdateMCPServerRequest,
)
from app.services.mcp_service import MCPService

router = APIRouter(prefix="/api/settings/mcp", tags=["mcp"])


@router.get("")
def list_mcp_servers(db=Depends(get_db)):
    """List all MCP servers with their tools."""
    try:
        data = MCPService(db).list_servers()
        return ok(MCPServersResponse(servers=data).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


@router.post("")
def create_mcp_server(request: CreateMCPServerRequest, db=Depends(get_db)):
    """Create a new MCP server."""
    try:
        data = MCPService(db).create_server(
            name=request.name,
            transport=request.transport,
            config_json=request.configJson,
        )
        return ok(data)
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


@router.post("/refresh")
async def refresh_mcp_tools(db=Depends(get_db)):
    """Discover tools from all enabled servers and refresh the tool registry."""
    try:
        result = await MCPService(db).refresh_tools()
        return ok(RefreshMCPResponse(**result).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


@router.patch("/tools/{tool_id}/enabled")
def set_mcp_tool_enabled(
    tool_id: str,
    request: SetMCPToolEnabledRequest,
    db=Depends(get_db),
):
    """Enable or disable an MCP tool."""
    data = MCPService(db).set_tool_enabled(tool_id, request.enabled)
    if data is None:
        return JSONResponse(status_code=404, content=err("Tool not found").model_dump())
    return ok(data)


@router.get("/{server_id}")
def get_mcp_server(server_id: str, db=Depends(get_db)):
    """Get a single MCP server with tools."""
    service = MCPService(db)
    servers = service.list_servers()
    found = next((s for s in servers if s["id"] == server_id), None)
    if not found:
        return JSONResponse(status_code=404, content=err("Server not found").model_dump())
    return ok(found)


@router.put("/{server_id}")
def update_mcp_server(
    server_id: str,
    request: UpdateMCPServerRequest,
    db=Depends(get_db),
):
    """Update an MCP server."""
    try:
        data = MCPService(db).update_server(
            server_id,
            name=request.name,
            transport=request.transport,
            config_json=request.configJson,
        )
        if data is None:
            return JSONResponse(status_code=404, content=err("Server not found").model_dump())
        return ok(data)
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


@router.delete("/{server_id}")
def delete_mcp_server(server_id: str, db=Depends(get_db)):
    """Delete an MCP server."""
    deleted = MCPService(db).delete_server(server_id)
    if not deleted:
        return JSONResponse(status_code=404, content=err("Server not found").model_dump())
    return ok({"deleted": True})


@router.patch("/{server_id}/enabled")
def set_mcp_server_enabled(
    server_id: str,
    request: SetMCPServerEnabledRequest,
    db=Depends(get_db),
):
    """Enable or disable an MCP server."""
    data = MCPService(db).set_server_enabled(server_id, request.enabled)
    if data is None:
        return JSONResponse(status_code=404, content=err("Server not found").model_dump())
    return ok(data)
