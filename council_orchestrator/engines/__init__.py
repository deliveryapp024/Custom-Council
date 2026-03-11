"""Planning engine factory."""

from __future__ import annotations

from .base import PlanningEngine
from .litellm_engine import LiteLLMEngine
from .opencode_engine import OpenCodeCLIEngine


def get_engine(engine_name: str) -> PlanningEngine:
    if engine_name == "litellm":
        return LiteLLMEngine()
    if engine_name == "opencode_cli":
        return OpenCodeCLIEngine()
    raise ValueError(f"Unsupported planning engine: {engine_name}")
