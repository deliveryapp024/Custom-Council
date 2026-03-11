"""FastAPI REST API + SSE streaming for the council orchestrator."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..config import load_config
from ..council.engine import (
    calculate_aggregate_rankings,
    run_stage1,
    run_stage2,
    run_stage3,
)
from ..schemas import AggregateRanking, Stage1Result, Stage2Result
from . import run_store

router = APIRouter(prefix="/api")

# ── In-memory SSE queues and tasks keyed by run_id ──
_sse_queues: dict[str, asyncio.Queue] = {}
_run_tasks: dict[str, asyncio.Task] = {}


# ── Request / response models ──

class RunRequest(BaseModel):
    task: str
    project_path: str


class ApproveRequest(BaseModel):
    pass


class EditRequest(BaseModel):
    feedback: str


# ── Helper: serialise Pydantic / dataclass objects ──

def _to_dict(obj: Any) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return dict(obj)


# ── SSE push helper ──

async def _push(run_id: str, event: str, data: Any) -> None:
    q = _sse_queues.get(run_id)
    if q:
        await q.put({"event": event, "data": json.dumps(data, default=str)})


# ── Background runner ──

async def _run_pipeline(run_id: str, task: str, project_path: str) -> None:
    """Run the full 3-stage pipeline, pushing SSE events as results arrive."""
    config = load_config("config.yml")
    run = run_store.load_run(run_id)
    if run is None:
        return
    start = time.monotonic()

    try:
        # ── Stage 1 ──
        members = [
            m for m in config.council_members if m.enabled
        ]
        run["status"] = "stage1"
        run_store.save_run(run)
        await _push(run_id, "stage1_start", {
            "members": [m.name for m in members],
        })

        async def on_member_done(result: Stage1Result) -> None:
            d = _to_dict(result)
            run["stage1_results"].append(d)
            run_store.save_run(run)
            await _push(run_id, "stage1_member_done", d)

        stage1_results = await run_stage1(task, config, on_member_done=on_member_done)

        ok = sum(1 for r in stage1_results if r.ok)
        await _push(run_id, "stage1_complete", {
            "ok_count": ok,
            "fail_count": len(stage1_results) - ok,
        })

        # ── Stage 2 ──
        run["status"] = "stage2"
        run_store.save_run(run)

        review_count = sum(1 for r in stage1_results if r.ok)
        await _push(run_id, "stage2_start", {"review_count": review_count})

        async def on_review_done(result: Stage2Result) -> None:
            d = _to_dict(result)
            run["stage2_results"].append(d)
            run_store.save_run(run)
            await _push(run_id, "stage2_review_done", d)

        stage2_results, aggregate_rankings = await run_stage2(
            task, stage1_results, config, on_review_done=on_review_done,
        )

        run["aggregate_rankings"] = [_to_dict(r) for r in aggregate_rankings]
        run_store.save_run(run)
        await _push(run_id, "stage2_complete", {
            "ok_count": sum(1 for r in stage2_results if r.ok),
            "fail_count": sum(1 for r in stage2_results if not r.ok),
            "aggregate_rankings": [_to_dict(r) for r in aggregate_rankings],
        })

        # ── Stage 3 ──
        run["status"] = "stage3"
        run_store.save_run(run)
        await _push(run_id, "stage3_start", {"chairman": config.chairman.name})

        chairman_output = await run_stage3(
            task, stage1_results, stage2_results, config,
        )

        run["chairman_output"] = chairman_output
        run["status"] = "awaiting_approval"
        run["duration_ms"] = int((time.monotonic() - start) * 1000)
        run_store.save_run(run)
        await _push(run_id, "stage3_complete", {"plan": chairman_output})

    except Exception as exc:
        run["status"] = "error"
        run["error"] = str(exc)
        run["duration_ms"] = int((time.monotonic() - start) * 1000)
        run_store.save_run(run)
        await _push(run_id, "error", {"message": str(exc)})
    except asyncio.CancelledError:
        run["status"] = "error"
        run["error"] = "Run cancelled by user."
        run["duration_ms"] = int((time.monotonic() - start) * 1000)
        run_store.save_run(run)
        await _push(run_id, "error", {"message": "Run cancelled by user."})
        raise
    finally:
        await _push(run_id, "done", {})
        _run_tasks.pop(run_id, None)


# ══════════════════════════════════════════════
#  REST  ENDPOINTS
# ══════════════════════════════════════════════

@router.post("/runs")
async def create_run(body: RunRequest) -> dict:
    """Start a new council run.  Returns the run_id immediately."""
    run = run_store.new_run(body.task, body.project_path)
    run_id = run["id"]

    # Create SSE queue before scheduling the pipeline
    _sse_queues[run_id] = asyncio.Queue()
    task_obj = asyncio.create_task(_run_pipeline(run_id, body.task, body.project_path))
    _run_tasks[run_id] = task_obj

    return {"id": run_id, "status": "running"}


@router.get("/runs")
async def list_runs() -> list[dict]:
    """List all past runs (summary only)."""
    return run_store.list_runs()


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    """Get full run details."""
    run = run_store.load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    """SSE stream — real-time stage progress."""
    run = run_store.load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    q = _sse_queues.get(run_id)
    if q is None:
        # Run already completed — send current state
        async def replay():
            yield {"event": "snapshot", "data": json.dumps(run, default=str)}
            yield {"event": "done", "data": "{}"}
        return EventSourceResponse(replay())

    async def event_generator():
        while True:
            msg = await q.get()
            yield msg
            if msg.get("event") == "done":
                _sse_queues.pop(run_id, None)
                break

    return EventSourceResponse(event_generator())


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: str) -> dict:
    """Approve the chairman's plan."""
    run = run_store.load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run["status"] != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Cannot approve run with status: {run['status']}")
    run["status"] = "approved"
    run_store.save_run(run)
    return {"status": "approved"}


@router.post("/runs/{run_id}/reject")
async def reject_run(run_id: str) -> dict:
    """Reject the plan."""
    run = run_store.load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run["status"] = "rejected"
    run_store.save_run(run)
    return {"status": "rejected"}


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str) -> dict:
    """Stop/cancel a running pipeline."""
    run = run_store.load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    t = _run_tasks.get(run_id)
    if t and not t.done():
        t.cancel()
    
    # We update the backend JSON immediately as well
    if run["status"] not in ["error", "approved", "rejected", "done"]:
        run["status"] = "error"
        run["error"] = "Run cancelled by user."
        run_store.save_run(run)
        
    return {"status": "error", "message": "Cancelled"}


@router.post("/runs/{run_id}/edit")
async def edit_run(run_id: str, body: EditRequest) -> dict:
    """Submit feedback and re-run chairman (Stage 3 only)."""
    run = run_store.load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    # TODO: re-run stage3 with feedback — for now just save feedback
    run["status"] = "editing"
    run["edit_feedback"] = body.feedback
    run_store.save_run(run)
    return {"status": "editing", "message": "Feedback saved, re-run not yet implemented"}


@router.get("/config")
async def get_config() -> dict:
    """Return current config as JSON."""
    config = load_config("config.yml")
    return config.model_dump()
