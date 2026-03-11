"""Minimal HTTP MCP client for JSON-RPC style MCP endpoints."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

from ..schemas import MCPServerConfig


class HTTPMCPClient:
    def __init__(self, server: MCPServerConfig) -> None:
        self.server = server
        self._request_id = 0
        self._client: httpx.AsyncClient | None = None
        self._session_id: str | None = None

    async def __aenter__(self) -> "HTTPMCPClient":
        self._client = httpx.AsyncClient(timeout=30.0)
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def initialize(self) -> Any:
        return await self.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {
                    "name": "council-orchestrator",
                    "version": "0.1.0",
                },
            },
        )

    async def list_tools(self) -> Any:
        return await self.request("tools/list", {})

    async def list_resources(self) -> Any:
        return await self.request("resources/list", {})

    async def read_resource(self, uri: str) -> Any:
        return await self.request("resources/read", {"uri": uri})

    async def list_prompts(self) -> Any:
        return await self.request("prompts/list", {})

    async def get_prompt(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return await self.request("prompts/get", {"name": name, "arguments": arguments or {}})

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return await self.request("tools/call", {"name": name, "arguments": arguments or {}})

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        client = self._require_client()
        headers = await self._build_headers()
        self._request_id += 1
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        response = await client.post(
            self.server.url,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                **headers,
            },
            json={
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params or {},
            },
        )
        self._capture_session(response)
        if response.status_code >= 400:
            raise RuntimeError(self._format_http_error(method, response))
        payload = self._parse_response_payload(method, response)
        if "error" in payload:
            fallback = _unsupported_method_fallback(method, payload["error"])
            if fallback is not None:
                return fallback
            raise RuntimeError(f"MCP {self.server.id} request {method} failed: {payload['error']}")
        return payload.get("result")

    def _require_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("HTTP MCP client is not initialized")
        return self._client

    def _capture_session(self, response: httpx.Response) -> None:
        session_id = response.headers.get("Mcp-Session-Id") or response.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id.strip()

    async def _build_headers(self) -> dict[str, str]:
        headers = dict(self.server.headers)
        auth_value = headers.get("Authorization", "")
        if self.server.id == "github" and auth_value.strip() in {"", "Bearer"}:
            token = await _github_pat_fallback()
            if token:
                headers["Authorization"] = f"Bearer {token}"
            else:
                headers.pop("Authorization", None)
        if self.server.id == "supabase-remote" and auth_value.strip() in {"", "Bearer"}:
            token = os.environ.get("SUPABASE_ACCESS_TOKEN", "").strip()
            if token:
                headers["Authorization"] = f"Bearer {token}"
            else:
                headers.pop("Authorization", None)
        if headers.get("Authorization", "").strip() in {"", "Bearer"}:
            headers.pop("Authorization", None)
        return headers

    def _parse_response_payload(self, method: str, response: httpx.Response) -> dict[str, Any]:
        text = response.text.strip()
        if not text:
            raise RuntimeError(
                f"MCP {self.server.id} request {method} returned an empty response body "
                f"with HTTP {response.status_code}. This usually means the remote server expects "
                "a different transport mode or the auth flow was rejected."
            )
        try:
            return response.json()
        except ValueError:
            pass

        sse_payload = _parse_sse_payload(text)
        if sse_payload is not None:
            return sse_payload

        snippet = text[:500]
        raise RuntimeError(
            f"MCP {self.server.id} request {method} returned non-JSON content "
            f"(HTTP {response.status_code}): {snippet}"
        )

    def _format_http_error(self, method: str, response: httpx.Response) -> str:
        body = response.text.strip()
        if self.server.id == "supabase-remote" and response.status_code == 401:
            has_token = bool(os.environ.get("SUPABASE_ACCESS_TOKEN", "").strip())
            has_project_ref = bool(os.environ.get("SUPABASE_PROJECT_REF", "").strip())
            details = body[:500] if body else "Unauthorized"
            token_hint = (
                "SUPABASE_ACCESS_TOKEN is missing."
                if not has_token
                else "SUPABASE_ACCESS_TOKEN was sent but was rejected."
            )
            project_hint = (
                " SUPABASE_PROJECT_REF is configured."
                if has_project_ref
                else " SUPABASE_PROJECT_REF is not set, so the server is not project-scoped."
            )
            return (
                f"MCP {self.server.id} request {method} failed with HTTP 401: {details} "
                f"For the hosted Supabase MCP server, this custom client needs a valid personal access token. "
                f"{token_hint}{project_hint}"
            )
        if body:
            return (
                f"MCP {self.server.id} request {method} failed with HTTP {response.status_code}: "
                f"{body[:500]}"
            )
        return f"MCP {self.server.id} request {method} failed with HTTP {response.status_code}"


async def _github_pat_fallback() -> str:
    try:
        process = await asyncio.create_subprocess_exec(
            "gh",
            "auth",
            "token",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return ""

    stdout, _stderr = await process.communicate()
    if process.returncode != 0:
        return ""
    return stdout.decode("utf-8", errors="ignore").strip()


def _parse_sse_payload(body: str) -> dict[str, Any] | None:
    blocks = [block for block in body.split("\n\n") if block.strip()]
    for block in blocks:
        data_lines: list[str] = []
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(":"):
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if not data_lines:
            continue
        data_text = "\n".join(data_lines).strip()
        if not data_text:
            continue
        try:
            return json.loads(data_text)
        except json.JSONDecodeError:
            continue
    return None


def _unsupported_method_fallback(method: str, error: Any) -> dict[str, Any] | None:
    if not isinstance(error, dict):
        return None
    if error.get("code") != -32601:
        return None
    if method == "resources/list":
        return {"resources": []}
    if method == "prompts/list":
        return {"prompts": []}
    return None
