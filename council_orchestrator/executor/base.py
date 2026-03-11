"""Execution agent abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ExecutionAgent(ABC):
    @abstractmethod
    def run_plan(self, workspace_path: str, plan_text: str) -> int:
        """Execute the approved plan and return an exit code."""

    @abstractmethod
    def send_followup(self, workspace_path: str, error_text: str) -> int:
        """Send a fix prompt and return an exit code."""
