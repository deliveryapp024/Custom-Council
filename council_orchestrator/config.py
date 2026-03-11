"""Configuration loading utilities."""

from __future__ import annotations

from pathlib import Path

import yaml
from dotenv import load_dotenv

from .schemas import AppConfig, CouncilMember


def load_config(config_path: str | Path) -> AppConfig:
    path = Path(config_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    env_path = path.parent / ".env"
    loaded = load_dotenv(env_path, override=True)
    if loaded:
        print(f"Loaded environment from: {env_path}")
    else:
        print(f"WARNING: No .env file found at: {env_path}")

    # Diagnostic: show which API keys are set (masked)
    import os
    for key_name in ["OPENROUTER_API_KEY", "GEMINI_API_KEY", "ZAI_API_KEY", "MOONSHOT_API_KEY"]:
        value = os.environ.get(key_name, "")
        if value:
            print(f"  ✓ {key_name} = {value[:8]}...{value[-4:]}")
        else:
            print(f"  ✗ {key_name} = NOT SET")

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    return AppConfig.model_validate(raw)


def enabled_council_members(config: AppConfig) -> list[CouncilMember]:
    return [member for member in config.council_members if member.enabled]
