"""Configuration loading utilities with in-memory caching."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .config_overrides import apply_mcp_overrides, overrides_signature
from .skill_catalog import merge_discovered_skills
from .schemas import AppConfig, CouncilMember, SkillSourceConfig

_cache_lock = threading.Lock()
_config_cache: dict[tuple[str, tuple[Any, ...]], AppConfig] = {}


def load_config(config_path: str | Path, *, force_reload: bool = False) -> AppConfig:
    path = Path(config_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = _load_raw_yaml(path)
    signature = _build_config_signature(path, raw)
    cache_key = (str(path), signature)

    with _cache_lock:
        if not force_reload and cache_key in _config_cache:
            return _config_cache[cache_key]
        if force_reload:
            _config_cache.clear()
        else:
            stale_keys = [key for key in _config_cache if key[0] == str(path) and key != cache_key]
            for key in stale_keys:
                _config_cache.pop(key, None)

    _load_environment(path)
    _print_env_diagnostics()
    merged = _expand_env_placeholders(raw)
    merged = merge_discovered_skills(merged)
    merged = apply_mcp_overrides(merged)
    config = AppConfig.model_validate(merged)

    with _cache_lock:
        _config_cache[cache_key] = config
    return config


def reload_config(config_path: str | Path) -> AppConfig:
    return load_config(config_path, force_reload=True)


def clear_config_cache() -> None:
    with _cache_lock:
        _config_cache.clear()


def enabled_council_members(config: AppConfig) -> list[CouncilMember]:
    return [member for member in config.council_members if member.enabled]


def _load_raw_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _expand_env_placeholders(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env_placeholders(item) for item in value]
    if isinstance(value, str):
        return _replace_env_vars(value)
    return value


def _replace_env_vars(text: str) -> str:
    result = text
    start = 0
    while True:
        open_index = result.find("${", start)
        if open_index == -1:
            return result
        close_index = result.find("}", open_index + 2)
        if close_index == -1:
            return result
        key = result[open_index + 2 : close_index]
        replacement = os.environ.get(key, "")
        result = result[:open_index] + replacement + result[close_index + 1 :]
        start = open_index + len(replacement)


def _load_environment(path: Path) -> None:
    env_path = path.parent / ".env"
    loaded = load_dotenv(env_path, override=True)
    if loaded:
        print(f"Loaded environment from: {env_path}")
    else:
        print(f"WARNING: No .env file found at: {env_path}")


def _print_env_diagnostics() -> None:
    for key_name in ["OPENROUTER_API_KEY", "GEMINI_API_KEY", "ZAI_API_KEY", "MOONSHOT_API_KEY"]:
        value = os.environ.get(key_name, "")
        if value:
            print(f"  [OK] {key_name} = {value[:8]}...{value[-4:]}")
        else:
            print(f"  [MISSING] {key_name} = NOT SET")
    supabase_token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if supabase_token:
        print(f"  [OK] SUPABASE_ACCESS_TOKEN = {supabase_token[:8]}...{supabase_token[-4:]}")
    else:
        print("  [MISSING] SUPABASE_ACCESS_TOKEN = NOT SET")
    supabase_project_ref = os.environ.get("SUPABASE_PROJECT_REF", "")
    if supabase_project_ref:
        print(f"  [OK] SUPABASE_PROJECT_REF = {supabase_project_ref}")
    else:
        print("  [MISSING] SUPABASE_PROJECT_REF = NOT SET")


def _build_config_signature(path: Path, raw: dict[str, Any]) -> tuple[Any, ...]:
    config_stat = path.stat()
    env_signature = _env_file_signature(path.parent / ".env")
    skill_sources = [SkillSourceConfig.model_validate(item) for item in raw.get("skill_sources", []) or []]
    root_signatures = tuple(_skill_root_signature(source) for source in skill_sources)
    return (
        path.as_posix(),
        config_stat.st_mtime_ns,
        config_stat.st_size,
        env_signature,
        root_signatures,
        overrides_signature(),
    )


def _env_file_signature(path: Path) -> tuple[Any, ...]:
    if not path.exists():
        return (str(path), False, 0, 0)
    stat = path.stat()
    return (str(path.resolve()), True, stat.st_mtime_ns, stat.st_size)


def _skill_root_signature(source: SkillSourceConfig) -> tuple[Any, ...]:
    root = Path(source.path).expanduser()
    if not root.exists():
        return (source.source_name, str(root), False, 0, 0, 0)

    root_stat = root.stat()
    pattern = "**/SKILL.md" if source.recursive else "*/SKILL.md"
    skill_files = list(root.glob(pattern))
    latest_file_mtime = max((skill_file.stat().st_mtime_ns for skill_file in skill_files), default=0)
    file_count = len(skill_files)
    return (
        source.source_name,
        str(root.resolve()),
        True,
        root_stat.st_mtime_ns,
        latest_file_mtime,
        file_count,
    )
