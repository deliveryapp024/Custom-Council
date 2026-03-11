"""Execution agent factory."""

from __future__ import annotations

from ..schemas import ExecutorConfig
from .aider_agent import AiderExecutionAgent
from .base import ExecutionAgent
from .opencode_agent import OpenCodeExecutionAgent


def get_executor(config: ExecutorConfig) -> ExecutionAgent:
    if config.agent == "opencode":
        return OpenCodeExecutionAgent(model=config.model)
    if config.agent == "aider":
        return AiderExecutionAgent(model=config.model)
    raise ValueError(f"Unsupported execution agent: {config.agent}")
