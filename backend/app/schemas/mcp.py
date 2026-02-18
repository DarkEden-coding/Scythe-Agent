"""MCP server and tool schemas for API."""

from pydantic import BaseModel, Field


class MCPToolOut(BaseModel):
    id: str
    serverId: str
    toolName: str
    description: str | None
    enabled: bool
    discoveredAt: str


class MCPServerOut(BaseModel):
    id: str
    name: str
    transport: str
    configJson: str
    enabled: bool
    lastConnectedAt: str | None
    tools: list[MCPToolOut] = []


class MCPServersResponse(BaseModel):
    servers: list[MCPServerOut]


class CreateMCPServerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    transport: str = Field(min_length=1, max_length=50)
    configJson: str = Field(min_length=1)


class UpdateMCPServerRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=500)
    transport: str | None = Field(None, min_length=1, max_length=50)
    configJson: str | None = None


class SetMCPServerEnabledRequest(BaseModel):
    enabled: bool


class SetMCPToolEnabledRequest(BaseModel):
    enabled: bool


class RefreshMCPResponse(BaseModel):
    success: bool
    discoveredCount: int
    errors: list[str] = []
