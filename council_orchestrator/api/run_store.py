"""JSON-file-based storage for council run data."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path("data/runs")


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def new_run(task: str, project_path: str) -> dict[str, Any]:
    """Create a new run record and persist it."""
    run = {
        "id": uuid.uuid4().hex[:12],
        "task": task,
        "project_path": project_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "stage1_results": [],
        "stage2_results": [],
        "aggregate_rankings": [],
        "chairman_output": "",
        "duration_ms": 0,
        "error": None,
    }
    save_run(run)
    return run


def save_run(run: dict[str, Any]) -> None:
    """Persist a run record to disk."""
    _ensure_dir()
    path = DATA_DIR / f"{run['id']}.json"
    path.write_text(json.dumps(run, indent=2, default=str), encoding="utf-8")


def load_run(run_id: str) -> dict[str, Any] | None:
    """Load a single run by ID.  Returns None if not found."""
    path = DATA_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_runs() -> list[dict[str, Any]]:
    """Return all runs sorted newest-first (summary fields only)."""
    _ensure_dir()
    runs: list[dict[str, Any]] = []
    for path in DATA_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            runs.append({
                "id": data["id"],
                "task": data["task"],
                "status": data["status"],
                "created_at": data["created_at"],
                "duration_ms": data.get("duration_ms", 0),
                "members_ok": sum(
                    1 for r in data.get("stage1_results", []) if r.get("ok")
                ),
                "members_total": len(data.get("stage1_results", [])),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    runs.sort(key=lambda r: r["created_at"], reverse=True)
    return runs
