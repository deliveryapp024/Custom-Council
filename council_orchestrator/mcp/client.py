"""Factory for MCP transport clients."""

from __future__ import annotations

from typing import Any

from ..schemas import MCPServerConfig
from .http_client import HTTPMCPClient
from .stdio_client import StdioMCPClient


def get_mcp_client(server: MCPServerConfig) -> Any:
    if server.transport == "stdio":
        return StdioMCPClient(server)
    if server.transport == "http":
        return HTTPMCPClient(server)
    raise ValueError(f"Unsupported MCP transport: {server.transport}")
