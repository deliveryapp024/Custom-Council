"""OpenCode execution agent."""

from __future__ import annotations

import subprocess

from .base import ExecutionAgent, ExecutionResult


class OpenCodeExecutionAgent(ExecutionAgent):
    def __init__(self, model: str = "openai/gpt-4o") -> None:
        self.model = model

    def run_plan(self, workspace_path: str, plan_text: str) -> ExecutionResult:
        prompt = (
            "Follow this approved implementation plan exactly. "
            "Modify code in the current workspace, run any needed edits, and stop when done.\n\n"
            f"{plan_text}"
        )
        command = ["opencode", "run"]
        if self.model:
            command.extend(["--model", self.model])
        command.append(prompt)
        result = subprocess.run(
            command,
            cwd=workspace_path,
            check=False,
            capture_output=True,
            text=True,
        )
        return ExecutionResult(
            exit_code=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )

    def send_followup(self, workspace_path: str, error_text: str) -> ExecutionResult:
        prompt = (
            "The last implementation attempt failed validation. "
            "Fix the code in the current workspace using this failure output.\n\n"
            f"{error_text}"
        )
        command = ["opencode", "run"]
        if self.model:
            command.extend(["--model", self.model])
        command.append(prompt)
        result = subprocess.run(
            command,
            cwd=workspace_path,
            check=False,
            capture_output=True,
            text=True,
        )
        return ExecutionResult(
            exit_code=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )
