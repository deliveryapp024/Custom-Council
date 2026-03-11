"""Planning engine backed by LiteLLM."""

from __future__ import annotations

import time

import litellm

# Suppress noisy LiteLLM debug messages (Provider List, feedback URLs, etc.)
litellm.suppress_debug_info = True
import logging as _logging
_logging.getLogger("LiteLLM").setLevel(_logging.WARNING)
_logging.getLogger("litellm").setLevel(_logging.WARNING)

from .base import EngineResponse, PlanningEngine


class LiteLLMEngine(PlanningEngine):
    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        member_name: str,
        timeout: int,
        api_base: str | None = None,
        api_key: str | None = None,
    ) -> EngineResponse:
        start = time.monotonic()
        try:
            kwargs: dict = dict(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
            if api_base:
                kwargs["api_base"] = api_base
            if api_key:
                kwargs["api_key"] = api_key

            response = await litellm.acompletion(**kwargs)
            text = response.choices[0].message.content or ""
            duration_ms = int((time.monotonic() - start) * 1000)
            return EngineResponse(
                ok=True,
                text=text,
                member_name=member_name,
                engine="litellm",
                model=model,
                duration_ms=duration_ms,
                raw=response,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            print(f"  ✗ LiteLLM FAILED for {member_name} (model={model}): {exc}")
            return EngineResponse(
                ok=False,
                text="",
                member_name=member_name,
                engine="litellm",
                model=model,
                duration_ms=duration_ms,
                error=str(exc),
            )

