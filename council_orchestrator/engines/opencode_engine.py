"""Planning engine backed by the OpenCode CLI."""

from __future__ import annotations

import asyncio
import json
import logging

import sys
import tempfile
import time
from pathlib import Path

from .base import EngineResponse, PlanningEngine

logger = logging.getLogger(__name__)


class OpenCodeCLIEngine(PlanningEngine):
    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        member_name: str,
        timeout: int,
        **kwargs,
    ) -> EngineResponse:
        start = time.monotonic()
        try:
            # Write the prompt to a temp file so we don't have to deal
            # with shell quoting for long, multi-line prompts.
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            )
            tmp.write(prompt)
            tmp.close()
            prompt_path = tmp.name

            try:
                text = await self._call_opencode(
                    prompt_path, model=model, timeout=timeout
                )
            finally:
                Path(prompt_path).unlink(missing_ok=True)

            if not text.strip():
                raise RuntimeError(
                    "OpenCode returned empty output."
                )

            duration_ms = int((time.monotonic() - start) * 1000)
            return EngineResponse(
                ok=True,
                text=text,
                member_name=member_name,
                engine="opencode_cli",
                model=model,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error("OpenCode engine failed for %s: %s", member_name, exc)
            return EngineResponse(
                ok=False,
                text="",
                member_name=member_name,
                engine="opencode_cli",
                model=model,
                duration_ms=duration_ms,
                error=str(exc),
            )

    async def _call_opencode(
        self, prompt_file: str, *, model: str, timeout: int
    ) -> str:
        prompt_text = Path(prompt_file).read_text(encoding="utf-8")

        command = ["opencode", "run"]
        if model:
            command.extend(["--model", model])
        command.extend(["--format", "json"])
        # Pass prompt via stdin instead of command line to avoid Windows 32KB limit

        if sys.platform == "win32":
            # On Windows, `opencode` is an npm wrapper (.cmd / .ps1).
            # Using create_subprocess_shell goes through cmd.exe which
            # has an ~8191-character command-line limit.  Instead, we
            # resolve node.exe + the opencode JS entry-point and call
            # create_subprocess_exec directly.  The Win32 CreateProcess
            # API supports ~32 767 characters — plenty for large prompts.
            resolved_command = self._resolve_opencode_for_windows(command)
            process = await asyncio.create_subprocess_exec(
                *resolved_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=prompt_text.encode("utf-8")), timeout=timeout,
        )
        raw_stdout = stdout.decode("utf-8", errors="replace")
        raw_stderr = stderr.decode("utf-8", errors="replace")

        if process.returncode != 0:
            raise RuntimeError(
                f"opencode exited with code {process.returncode}: {raw_stderr[:500]}"
            )

        return self._parse_opencode_output(raw_stdout)

    @staticmethod
    def _resolve_opencode_for_windows(command: list[str]) -> list[str]:
        """Resolve the npm opencode wrapper to node.exe + JS entry-point.

        This lets us use create_subprocess_exec (CreateProcess API,
        ~32K char limit) instead of create_subprocess_shell (cmd.exe,
        ~8K limit).
        """
        import shutil

        # Try to find the .cmd wrapper to locate the npm prefix.
        cmd_path = shutil.which("opencode") or shutil.which("opencode.cmd")
        if cmd_path:
            npm_dir = Path(cmd_path).resolve().parent
            # The npm wrapper calls: node <npm_dir>/node_modules/opencode-ai/bin/opencode
            entry_point = npm_dir / "node_modules" / "opencode-ai" / "bin" / "opencode"
            if entry_point.exists():
                node_exe = shutil.which("node") or "node.exe"
                # Replace "opencode" with [node.exe, entry_point]
                return [node_exe, str(entry_point)] + command[1:]

        # Fallback: cannot resolve, return command as-is.
        # This may hit the shell limit for very large prompts.
        logger.warning(
            "Could not resolve opencode entry-point; falling back to "
            "direct invocation (may hit Windows command-line length limit)"
        )
        return command

    def _parse_opencode_output(self, raw: str) -> str:
        lines = raw.strip().splitlines()
        collected: list[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            content = self._extract_text(event)
            if content:
                collected.append(content)

        if collected:
            return "\n".join(collected)

        try:
            blob = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Could not parse OpenCode JSON output, using raw text")
            return raw

        content = self._extract_text(blob)
        if content:
            return content

        logger.warning("Could not extract structured text from OpenCode output, using raw text")
        return raw

    def _extract_text(self, payload: object) -> str:
        if isinstance(payload, str):
            return payload
        if not isinstance(payload, dict):
            return ""

        for key in ("content", "text", "output", "result"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value

        part = payload.get("part")
        if isinstance(part, dict):
            return self._extract_text(part)

        message = payload.get("message")
        if isinstance(message, dict):
            return self._extract_text(message)

        data = payload.get("data")
        if isinstance(data, dict):
            return self._extract_text(data)

        return ""
