"""Planning engine abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class EngineResponse:
    ok: bool
    text: str
    member_name: str
    engine: str
    model: str
    duration_ms: int
    error: str | None = None
    raw: Any = None


class PlanningEngine(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        member_name: str,
        timeout: int,
        **kwargs,
    ) -> EngineResponse:
        """Send a prompt and get back text."""
