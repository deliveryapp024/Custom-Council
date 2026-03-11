"""Persistent config overrides for operator-managed settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


OVERRIDES_PATH = Path("data/config_overrides/mcp_server_flags.json")


def load_mcp_server_overrides() -> dict[str, bool]:
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        payload = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(server_id): bool(enabled)
        for server_id, enabled in payload.items()
    }


def set_mcp_server_override(server_id: str, enabled: bool) -> dict[str, bool]:
    overrides = load_mcp_server_overrides()
    overrides[server_id] = enabled
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDES_PATH.write_text(
        json.dumps(overrides, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return overrides


def overrides_signature() -> tuple[int, int]:
    if not OVERRIDES_PATH.exists():
        return (0, 0)
    stat = OVERRIDES_PATH.stat()
    return (stat.st_mtime_ns, stat.st_size)


def apply_mcp_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    overrides = load_mcp_server_overrides()
    if not overrides:
        return raw

    merged = dict(raw)
    servers = [dict(item) for item in merged.get("mcp_servers", []) or []]
    for server in servers:
        server_id = str(server.get("id", ""))
        if server_id in overrides:
            server["enabled"] = overrides[server_id]
    merged["mcp_servers"] = servers
    return merged
