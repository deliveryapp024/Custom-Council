"""OpenCode execution agent."""

from __future__ import annotations

import subprocess

from .base import ExecutionAgent


class OpenCodeExecutionAgent(ExecutionAgent):
    def __init__(self, model: str = "openai/gpt-4o") -> None:
        self.model = model

    def run_plan(self, workspace_path: str, plan_text: str) -> int:
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
        )
        return result.returncode

    def send_followup(self, workspace_path: str, error_text: str) -> int:
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
        )
        return result.returncode
