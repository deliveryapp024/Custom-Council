"""Minimal stdio MCP client for tools, resources, and prompts."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from ..schemas import MCPServerConfig


class MCPClientError(RuntimeError):
    pass


class StdioMCPClient:
    def __init__(self, server: MCPServerConfig) -> None:
        self.server = server
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0

    async def __aenter__(self) -> "StdioMCPClient":
        env = os.environ.copy()
        env.update(self.server.env)
        self._process = await asyncio.create_subprocess_exec(
            self.server.command,
            *self.server.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

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
        process = self._require_process()
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await process.stdin.drain()

        while True:
            line = await process.stdout.readline()
            if not line:
                stderr = await process.stderr.read()
                raise MCPClientError(
                    f"MCP server {self.server.id} closed the connection. stderr: {stderr.decode('utf-8', errors='ignore')}"
                )

            message = json.loads(line.decode("utf-8"))
            if "id" not in message or message["id"] != self._request_id:
                continue
            if "error" in message:
                raise MCPClientError(
                    f"MCP {self.server.id} request {method} failed: {message['error']}"
                )
            return message.get("result")

    async def close(self) -> None:
        if self._process is None:
            return
        if self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
        self._process = None

    def _require_process(self) -> asyncio.subprocess.Process:
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise MCPClientError("MCP process is not running")
        return self._process
