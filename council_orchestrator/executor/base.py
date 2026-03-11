"""Execution agent abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    logs_path: str | None = None


class ExecutionAgent(ABC):
    @abstractmethod
    def run_plan(self, workspace_path: str, plan_text: str) -> ExecutionResult:
        """Execute the approved plan and return an exit code."""

    @abstractmethod
    def send_followup(self, workspace_path: str, error_text: str) -> ExecutionResult:
        """Send a fix prompt and return an exit code."""
