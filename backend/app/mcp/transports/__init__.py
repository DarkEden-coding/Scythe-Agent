"""MCP transport adapters: stdio (local, npx/uvx) and http (remote)."""

from app.mcp.client_manager import MCPClientManager
from app.mcp.transports.http_transport import HttpTransport
from app.mcp.transports.stdio import StdioTransport

MCPClientManager.register_transport_factory("stdio", StdioTransport)
MCPClientManager.register_transport_factory("http", HttpTransport)

