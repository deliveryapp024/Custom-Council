"""Project-aware MCP server resolution."""

from __future__ import annotations

from pathlib import Path

from ..schemas import AppConfig, MCPServerConfig, ProjectProfile


def resolve_project_profile(project_path: str, config: AppConfig) -> ProjectProfile | None:
    candidate = Path(project_path).expanduser().resolve()
    for profile in config.project_profiles:
        for root_path in profile.root_paths:
            root = Path(root_path).expanduser().resolve()
            if candidate == root or root in candidate.parents:
                return profile
    return None


def list_project_servers(
    project_path: str,
    config: AppConfig,
    *,
    include_disabled: bool = False,
) -> list[MCPServerConfig]:
    profile = resolve_project_profile(project_path, config)
    enabled_ids = set(profile.enabled_mcp_servers if profile else [])
    servers = [
        server for server in config.mcp_servers
        if include_disabled or server.enabled
    ]
    if not enabled_ids:
        return [server for server in servers if not server.project_ids]
    return [
        server
        for server in servers
        if server.id in enabled_ids or not server.project_ids
    ]


def get_server_for_project(project_path: str, server_id: str, config: AppConfig) -> MCPServerConfig:
    configured_servers = list_project_servers(project_path, config, include_disabled=True)
    configured = next((server for server in configured_servers if server.id == server_id), None)
    if configured is not None and not configured.enabled:
        raise ValueError(
            f"MCP server {server_id} is configured for project {project_path} but is disabled. "
            "Enable it in config.yml and configure auth before using it."
        )
    for server in list_project_servers(project_path, config):
        if server.id == server_id:
            return server
    raise ValueError(f"MCP server {server_id} is not enabled for project {project_path}")
