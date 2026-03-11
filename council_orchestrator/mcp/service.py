"""High-level MCP service operations."""

from __future__ import annotations

import os
from typing import Any

from ..schemas import AppConfig
from .client import get_mcp_client
from .registry import get_server_for_project, list_project_servers, resolve_project_profile


def describe_project_mcp(project_path: str, config: AppConfig) -> dict[str, Any]:
    profile = resolve_project_profile(project_path, config)
    servers = list_project_servers(project_path, config, include_disabled=True)
    return {
        "project_profile": profile.model_dump() if profile else None,
        "servers": [_server_view(server) for server in servers],
    }


def _server_view(server) -> dict[str, Any]:
    missing_env = [
        key for key in server.required_env
        if not os.environ.get(key, "").strip()
    ]
    return {
        **server.model_dump(),
        "missing_env": missing_env,
        "ready": server.enabled and not missing_env,
    }


async def list_server_tools(project_path: str, server_id: str, config: AppConfig) -> Any:
    server = get_server_for_project(project_path, server_id, config)
    async with get_mcp_client(server) as client:
        return await client.list_tools()


async def list_server_resources(project_path: str, server_id: str, config: AppConfig) -> Any:
    server = get_server_for_project(project_path, server_id, config)
    async with get_mcp_client(server) as client:
        return await client.list_resources()


async def read_server_resource(project_path: str, server_id: str, uri: str, config: AppConfig) -> Any:
    server = get_server_for_project(project_path, server_id, config)
    async with get_mcp_client(server) as client:
        return await client.read_resource(uri)


async def list_server_prompts(project_path: str, server_id: str, config: AppConfig) -> Any:
    server = get_server_for_project(project_path, server_id, config)
    async with get_mcp_client(server) as client:
        return await client.list_prompts()


async def get_server_prompt(
    project_path: str,
    server_id: str,
    name: str,
    arguments: dict[str, Any],
    config: AppConfig,
) -> Any:
    server = get_server_for_project(project_path, server_id, config)
    async with get_mcp_client(server) as client:
        return await client.get_prompt(name, arguments)


async def call_server_tool(
    project_path: str,
    server_id: str,
    name: str,
    arguments: dict[str, Any],
    config: AppConfig,
) -> Any:
    server = get_server_for_project(project_path, server_id, config)
    async with get_mcp_client(server) as client:
        return await client.call_tool(name, arguments)
