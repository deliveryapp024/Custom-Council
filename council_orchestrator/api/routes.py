"""FastAPI REST API + SSE streaming for the council orchestrator."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ..config import load_config, reload_config
from ..config_overrides import set_mcp_server_override
from ..council.engine import run_stage1, run_stage2, run_stage3
from ..mcp.service import (
    call_server_tool,
    describe_project_mcp,
    get_server_prompt,
    list_server_prompts,
    list_server_resources,
    list_server_tools,
    read_server_resource,
)
from ..mcp.registry import get_server_for_project
from ..schemas import ApprovalRecord, RunRecord, Stage1Result, Stage2Result, TaskRecord
from ..services.approval_service import record_plan_approval, record_task_approval
from ..services.assignment_service import create_assignment
from ..services.execution_service import execute_task
from ..services.mcp_approval_service import (
    approve_mcp_request,
    create_mcp_approval,
    execute_approved_mcp_request,
    fail_mcp_request,
    reject_mcp_request,
)
from ..services.qa_service import run_qa
from ..services.task_service import generate_tasks_for_run
from ..storage.repositories import (
    approval_repository,
    assignment_repository,
    mcp_approval_repository,
    new_id,
    qa_report_repository,
    run_repository,
    task_repository,
    utc_now_iso,
)
from . import run_store

router = APIRouter(prefix="/api")

CONFIG_PATH = "config.yml"
TERMINAL_RUN_STATUSES = {"completed", "rejected", "failed"}

_sse_queues: dict[str, asyncio.Queue] = {}
_run_tasks: dict[str, asyncio.Task] = {}


class RunRequest(BaseModel):
    task: str
    project_path: str


class EditRequest(BaseModel):
    feedback: str


class NotesRequest(BaseModel):
    notes: str = ""


class AssignRequest(BaseModel):
    agent_id: str
    selected_skills: list[str] = Field(default_factory=list)
    notes: str = ""


class MCPProjectRequest(BaseModel):
    project_path: str


class MCPPromptRequest(MCPProjectRequest):
    arguments: dict[str, Any] = Field(default_factory=dict)


class MCPResourceReadRequest(MCPProjectRequest):
    uri: str


class MCPToolCallRequest(MCPProjectRequest):
    arguments: dict[str, Any] = Field(default_factory=dict)
    approved_mutation: bool = False


class MCPApprovalCreateRequest(MCPProjectRequest):
    server_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class MCPServerEnabledRequest(BaseModel):
    enabled: bool


def _to_dict(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return obj


async def _push(run_id: str, event: str, data: Any) -> None:
    queue = _sse_queues.get(run_id)
    if queue is not None:
        await queue.put({"event": event, "data": json.dumps(data, default=str)})


async def _push_snapshot(run_id: str) -> None:
    run = run_store.load_run(run_id)
    if run is not None:
        await _push(run_id, "snapshot", run)


def _get_run_or_404(run_id: str) -> RunRecord:
    run = run_repository.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def _get_task_or_404(task_id: str) -> TaskRecord:
    task = task_repository.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _hydrate_task(task_id: str) -> dict[str, Any]:
    task = _get_task_or_404(task_id)
    return {
        **task.model_dump(),
        "assignments": [
            assignment.model_dump()
            for assignment in assignment_repository.list_for_task(task_id)
        ],
        "attempts": [
            attempt.model_dump()
            for attempt in task_repository_attempts(task_id)
        ],
        "qa_reports": [
            report.model_dump()
            for report in qa_report_repository.list_for_task(task_id)
        ],
        "approvals": [
            record.model_dump()
            for record in approval_repository.list_for_task(task_id)
        ],
    }


def task_repository_attempts(task_id: str):
    from ..storage.repositories import attempt_repository

    return attempt_repository.list_for_task(task_id)


def _latest_task_approval(task_id: str, gate: str) -> ApprovalRecord | None:
    approvals = [
        record
        for record in approval_repository.list_for_task(task_id)
        if record.gate == gate
    ]
    return approvals[-1] if approvals else None


def _validate_selected_skills(selected_skills: list[str], config) -> list[str]:
    valid_skill_ids = {skill.id for skill in config.skills}
    unknown = [skill_id for skill_id in selected_skills if skill_id not in valid_skill_ids]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown skill ids: {', '.join(sorted(unknown))}",
        )
    return selected_skills


def _refresh_run_status(run: RunRecord) -> RunRecord:
    tasks = task_repository.list_for_run(run.id)
    if not tasks:
        return run_repository.save(run)

    if all(task.status == "completed" for task in tasks):
        run.status = "completed"
    elif any(task.status == "executing" for task in tasks):
        run.status = "executing"
    elif any(task.status == "qa_review" and task.latest_qa_report_id is None for task in tasks):
        run.status = "awaiting_commit_approval"
    elif any(task.status == "qa_review" for task in tasks):
        run.status = "qa_review"
    elif any(task.status == "awaiting_completion_approval" for task in tasks):
        run.status = "awaiting_completion_approval"
    elif any(task.status == "execution_retry_needed" for task in tasks):
        run.status = "awaiting_execution_approval"
    elif any(task.status == "awaiting_execution_approval" for task in tasks):
        run.status = "awaiting_execution_approval"
    elif any(task.status == "awaiting_assignment" for task in tasks):
        run.status = "task_graph_ready"
    return run_repository.save(run)


async def _emit_terminal_if_needed(run: RunRecord) -> None:
    if run.status in TERMINAL_RUN_STATUSES:
        await _push(run.id, "done", {})
        _sse_queues.pop(run.id, None)


async def _generate_tasks(run: RunRecord, config) -> list[TaskRecord]:
    existing = task_repository.list_for_run(run.id)
    if existing:
        if not run.task_ids:
            run.task_ids = [task.id for task in existing]
        run.status = "task_graph_ready"
        run_repository.save(run)
        return existing

    tasks = await generate_tasks_for_run(run, config)
    run.task_ids = [task.id for task in tasks]
    run.status = "task_graph_ready"
    run_repository.save(run)
    return tasks


async def _run_pipeline(run_id: str, task: str) -> None:
    config = load_config(CONFIG_PATH)
    run = _get_run_or_404(run_id)
    start = time.monotonic()

    try:
        members = [member for member in config.council_members if member.enabled]
        run.status = "stage1"
        run_repository.save(run)
        await _push(run_id, "stage1_start", {"members": [member.name for member in members]})
        await _push_snapshot(run_id)

        async def on_member_done(result: Stage1Result) -> None:
            current = _get_run_or_404(run_id)
            current.stage1_results.append(result)
            run_repository.save(current)
            await _push(run_id, "stage1_member_done", _to_dict(result))
            await _push_snapshot(run_id)

        stage1_results = await run_stage1(task, config, on_member_done=on_member_done)

        run = _get_run_or_404(run_id)
        run.status = "stage2"
        run_repository.save(run)
        await _push(run_id, "stage2_start", {"review_count": sum(1 for result in stage1_results if result.ok)})
        await _push_snapshot(run_id)

        async def on_review_done(result: Stage2Result) -> None:
            current = _get_run_or_404(run_id)
            current.stage2_results.append(result)
            run_repository.save(current)
            await _push(run_id, "stage2_review_done", _to_dict(result))
            await _push_snapshot(run_id)

        stage2_results, aggregate_rankings = await run_stage2(
            task,
            stage1_results,
            config,
            on_review_done=on_review_done,
        )

        run = _get_run_or_404(run_id)
        run.aggregate_rankings = aggregate_rankings
        run.status = "stage3"
        run_repository.save(run)
        await _push(
            run_id,
            "stage2_complete",
            {
                "aggregate_rankings": [_to_dict(item) for item in aggregate_rankings],
                "ok_count": sum(1 for result in stage2_results if result.ok),
                "fail_count": sum(1 for result in stage2_results if not result.ok),
            },
        )
        await _push(run_id, "stage3_start", {"chairman": config.chairman.name})
        await _push_snapshot(run_id)

        plan = await run_stage3(task, stage1_results, stage2_results, config)

        run = _get_run_or_404(run_id)
        run.chairman_output = plan
        run.status = "awaiting_plan_approval"
        run.duration_ms = int((time.monotonic() - start) * 1000)
        run_repository.save(run)
        await _push(run_id, "stage3_complete", {"plan": plan})
        await _push(run_id, "approval_required", {"gate": "plan", "run_id": run_id})
        await _push_snapshot(run_id)
    except asyncio.CancelledError:
        run = _get_run_or_404(run_id)
        run.status = "failed"
        run.error = "Run cancelled by user."
        run.duration_ms = int((time.monotonic() - start) * 1000)
        run_repository.save(run)
        await _push(run_id, "error", {"message": run.error})
        await _push_snapshot(run_id)
        await _emit_terminal_if_needed(run)
        raise
    except Exception as exc:
        run = _get_run_or_404(run_id)
        run.status = "failed"
        run.error = str(exc)
        run.duration_ms = int((time.monotonic() - start) * 1000)
        run_repository.save(run)
        await _push(run_id, "error", {"message": str(exc)})
        await _push_snapshot(run_id)
        await _emit_terminal_if_needed(run)
    finally:
        _run_tasks.pop(run_id, None)


@router.post("/runs")
async def create_run(body: RunRequest) -> dict[str, Any]:
    run = run_store.new_run(body.task, body.project_path)
    run_id = run["id"]
    _sse_queues.setdefault(run_id, asyncio.Queue())
    _run_tasks[run_id] = asyncio.create_task(_run_pipeline(run_id, body.task))
    return {"id": run_id, "status": "running"}


@router.get("/runs")
async def list_runs() -> list[dict[str, Any]]:
    return run_store.list_runs()


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    run = run_store.load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    run = run_store.load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    queue = _sse_queues.get(run_id)
    if queue is None:
        async def replay():
            yield {"event": "snapshot", "data": json.dumps(run, default=str)}
            if run["status"] in TERMINAL_RUN_STATUSES:
                yield {"event": "done", "data": "{}"}

        return EventSourceResponse(replay())

    async def event_generator():
        yield {"event": "snapshot", "data": json.dumps(run, default=str)}
        while True:
            message = await queue.get()
            yield message
            if message.get("event") == "done":
                break

    return EventSourceResponse(event_generator())


@router.post("/runs/{run_id}/approve-plan")
async def approve_plan(run_id: str, body: NotesRequest) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    run = _get_run_or_404(run_id)
    if run.status != "awaiting_plan_approval":
        raise HTTPException(status_code=400, detail=f"Run is not awaiting plan approval: {run.status}")

    approval = record_plan_approval(run, "approved", body.notes)
    tasks = await _generate_tasks(_get_run_or_404(run_id), config)
    refreshed = _refresh_run_status(_get_run_or_404(run_id))

    await _push(run_id, "approval_recorded", approval.model_dump())
    await _push(run_id, "tasks_generated", {"run_id": run_id, "task_count": len(tasks)})
    await _push_snapshot(run_id)
    return run_store.load_run(refreshed.id) or {}


@router.post("/runs/{run_id}/reject-plan")
async def reject_plan(run_id: str, body: NotesRequest) -> dict[str, Any]:
    run = _get_run_or_404(run_id)
    if run.status not in {"awaiting_plan_approval", "task_graph_ready", "plan_approved"}:
        raise HTTPException(status_code=400, detail=f"Run cannot be rejected from status: {run.status}")

    approval = record_plan_approval(run, "rejected", body.notes)
    refreshed = _get_run_or_404(run_id)
    await _push(run_id, "approval_recorded", approval.model_dump())
    await _push_snapshot(run_id)
    await _emit_terminal_if_needed(refreshed)
    return run_store.load_run(run_id) or {}


@router.post("/runs/{run_id}/tasks/generate")
async def generate_run_tasks(run_id: str) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    run = _get_run_or_404(run_id)
    if run.status not in {"plan_approved", "task_graph_ready", "awaiting_execution_approval"}:
        raise HTTPException(status_code=400, detail=f"Run is not ready for task generation: {run.status}")

    tasks = await _generate_tasks(run, config)
    refreshed = _refresh_run_status(_get_run_or_404(run_id))
    await _push(run_id, "tasks_generated", {"run_id": run_id, "task_count": len(tasks)})
    await _push_snapshot(run_id)
    return run_store.load_run(refreshed.id) or {}


@router.get("/runs/{run_id}/tasks")
async def list_run_tasks(run_id: str) -> list[dict[str, Any]]:
    _get_run_or_404(run_id)
    return [_hydrate_task(task.id) for task in task_repository.list_for_run(run_id)]


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str) -> dict[str, Any]:
    run = _get_run_or_404(run_id)
    task = _run_tasks.get(run_id)
    if task is not None and not task.done():
        task.cancel()
    if run.status not in TERMINAL_RUN_STATUSES:
        run.status = "failed"
        run.error = "Run cancelled by user."
        run_repository.save(run)
        await _push(run_id, "error", {"message": run.error})
        await _push_snapshot(run_id)
        await _emit_terminal_if_needed(run)
    return {"status": run.status, "message": run.error or ""}


@router.post("/runs/{run_id}/edit")
async def edit_run(run_id: str, body: EditRequest) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    run = _get_run_or_404(run_id)
    if run.status != "awaiting_plan_approval":
        raise HTTPException(status_code=400, detail=f"Run is not awaiting plan approval: {run.status}")

    run.status = "stage3"
    run_repository.save(run)
    await _push(run_id, "stage3_start", {"chairman": config.chairman.name, "revision": True})
    await _push_snapshot(run_id)

    revised_plan = await run_stage3(
        run.task,
        run.stage1_results,
        run.stage2_results,
        config,
        feedback=body.feedback,
    )

    approval_repository.save(
        ApprovalRecord(
            id=new_id("approval"),
            gate="plan",
            decision="edited",
            run_id=run.id,
            notes=body.feedback,
            created_at=utc_now_iso(),
        )
    )
    run = _get_run_or_404(run_id)
    run.chairman_output = revised_plan
    run.status = "awaiting_plan_approval"
    run_repository.save(run)
    await _push(run_id, "stage3_complete", {"plan": revised_plan, "revision": True})
    await _push(run_id, "approval_required", {"gate": "plan", "run_id": run_id})
    await _push_snapshot(run_id)
    return run_store.load_run(run_id) or {}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict[str, Any]:
    return _hydrate_task(task_id)


@router.post("/tasks/{task_id}/assign")
async def assign_task(task_id: str, body: AssignRequest) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    task = _get_task_or_404(task_id)
    run = _get_run_or_404(task.run_id)
    selected_skills = _validate_selected_skills(body.selected_skills or task.recommended_skills, config)
    try:
        assignment = create_assignment(task, body.agent_id, selected_skills, config, notes=body.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    refreshed_run = _refresh_run_status(run)
    await _push(task.run_id, "task_assigned", assignment.model_dump())
    await _push(task.run_id, "approval_required", {"gate": "execution", "run_id": task.run_id, "task_id": task.id})
    await _push_snapshot(task.run_id)
    return {
        "task": _hydrate_task(task_id),
        "run_status": refreshed_run.status,
    }


@router.post("/tasks/{task_id}/approve-execution")
async def approve_execution(task_id: str, body: NotesRequest) -> dict[str, Any]:
    task = _get_task_or_404(task_id)
    if task.selected_agent_id is None:
        raise HTTPException(status_code=400, detail="Task must be assigned before execution approval")
    approval = record_task_approval(task, "execution", "approved", body.notes)
    run = _get_run_or_404(task.run_id)
    refreshed_run = _refresh_run_status(run)
    await _push(task.run_id, "approval_recorded", approval.model_dump())
    await _push_snapshot(task.run_id)
    return {
        "task": _hydrate_task(task_id),
        "run_status": refreshed_run.status,
    }


@router.post("/tasks/{task_id}/reject-execution")
async def reject_execution(task_id: str, body: NotesRequest) -> dict[str, Any]:
    task = _get_task_or_404(task_id)
    approval = record_task_approval(task, "execution", "rejected", body.notes)
    run = _get_run_or_404(task.run_id)
    refreshed_run = _refresh_run_status(run)
    await _push(task.run_id, "approval_recorded", approval.model_dump())
    await _push_snapshot(task.run_id)
    return {
        "task": _hydrate_task(task_id),
        "run_status": refreshed_run.status,
    }


@router.post("/tasks/{task_id}/execute")
async def execute_task_route(task_id: str) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    task = _get_task_or_404(task_id)
    run = _get_run_or_404(task.run_id)
    approval = _latest_task_approval(task_id, "execution")
    if task.selected_agent_id is None:
        raise HTTPException(status_code=400, detail="Task must be assigned before execution")
    if approval is None or approval.decision != "approved":
        raise HTTPException(status_code=400, detail="Task execution requires prior approval")

    task.status = "executing"
    task_repository.save(task)
    run.status = "executing"
    run_repository.save(run)
    await _push(task.run_id, "execution_started", {"run_id": run.id, "task_id": task.id})
    await _push_snapshot(task.run_id)

    attempt = await asyncio.to_thread(execute_task, task, run, config)
    run = _get_run_or_404(task.run_id)
    run.status = "awaiting_commit_approval" if attempt.exit_code == 0 and attempt.test_result == "passed" else "awaiting_execution_approval"
    run_repository.save(run)
    await _push(task.run_id, "execution_finished", {"run_id": run.id, "task_id": task.id, "attempt": attempt.model_dump()})
    await _push_snapshot(task.run_id)
    return {
        "task": _hydrate_task(task_id),
        "run_status": run.status,
    }


@router.post("/tasks/{task_id}/qa")
async def run_task_qa(task_id: str) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    task = _get_task_or_404(task_id)
    run = _get_run_or_404(task.run_id)
    if task.latest_attempt_id is None:
        raise HTTPException(status_code=400, detail="Task must be executed before QA")
    if task.status not in {"qa_review", "execution_retry_needed", "awaiting_completion_approval"}:
        raise HTTPException(status_code=400, detail=f"Task is not ready for QA: {task.status}")

    run.status = "qa_review"
    run_repository.save(run)
    await _push(task.run_id, "qa_started", {"run_id": run.id, "task_id": task.id})
    await _push_snapshot(task.run_id)

    report = await run_qa(task, run, config)
    refreshed_run = _refresh_run_status(_get_run_or_404(task.run_id))
    await _push(task.run_id, "qa_finished", {"run_id": refreshed_run.id, "task_id": task.id, "report": report.model_dump()})
    if task_repository.get(task_id) and task_repository.get(task_id).status == "awaiting_completion_approval":
        await _push(task.run_id, "approval_required", {"gate": "completion", "run_id": refreshed_run.id, "task_id": task.id})
    await _push_snapshot(task.run_id)
    return {
        "task": _hydrate_task(task_id),
        "run_status": refreshed_run.status,
    }


@router.post("/tasks/{task_id}/approve-completion")
async def approve_completion(task_id: str, body: NotesRequest) -> dict[str, Any]:
    task = _get_task_or_404(task_id)
    approval = record_task_approval(task, "completion", "approved", body.notes)
    run = _refresh_run_status(_get_run_or_404(task.run_id))
    await _push(task.run_id, "approval_recorded", approval.model_dump())
    await _push_snapshot(task.run_id)
    await _emit_terminal_if_needed(run)
    return {
        "task": _hydrate_task(task_id),
        "run_status": run.status,
    }


@router.post("/tasks/{task_id}/reject-completion")
async def reject_completion(task_id: str, body: NotesRequest) -> dict[str, Any]:
    task = _get_task_or_404(task_id)
    approval = record_task_approval(task, "completion", "rejected", body.notes)
    run = _refresh_run_status(_get_run_or_404(task.run_id))
    await _push(task.run_id, "approval_recorded", approval.model_dump())
    await _push_snapshot(task.run_id)
    return {
        "task": _hydrate_task(task_id),
        "run_status": run.status,
    }


@router.get("/agents")
async def list_agents() -> list[dict[str, Any]]:
    config = load_config(CONFIG_PATH)
    return [agent.model_dump() for agent in config.agents]


@router.get("/skills")
async def list_skills() -> list[dict[str, Any]]:
    config = load_config(CONFIG_PATH)
    return [skill.model_dump() for skill in config.skills]


@router.get("/config")
async def get_config() -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    return config.model_dump()


@router.post("/config/reload")
async def reload_current_config() -> dict[str, Any]:
    config = reload_config(CONFIG_PATH)
    return {
        "status": "reloaded",
        "skills": len(config.skills),
        "mcp_servers": len(config.mcp_servers),
        "project_profiles": len(config.project_profiles),
    }


@router.post("/mcp/servers/{server_id}/enabled")
async def set_mcp_server_enabled(server_id: str, body: MCPServerEnabledRequest) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    server = next((item for item in config.mcp_servers if item.id == server_id), None)
    if server is None:
        raise HTTPException(status_code=404, detail=f"Unknown MCP server: {server_id}")
    set_mcp_server_override(server_id, body.enabled)
    refreshed = reload_config(CONFIG_PATH)
    updated = next((item for item in refreshed.mcp_servers if item.id == server_id), None)
    return {
        "status": "updated",
        "server": updated.model_dump() if updated else None,
    }


@router.post("/mcp/projects/resolve")
async def resolve_mcp_project(body: MCPProjectRequest) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    return describe_project_mcp(body.project_path, config)


@router.post("/mcp/servers/{server_id}/tools")
async def mcp_list_tools(server_id: str, body: MCPProjectRequest) -> Any:
    config = load_config(CONFIG_PATH)
    try:
        return await list_server_tools(body.project_path, server_id, config)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/mcp/servers/{server_id}/resources")
async def mcp_list_resources(server_id: str, body: MCPProjectRequest) -> Any:
    config = load_config(CONFIG_PATH)
    try:
        return await list_server_resources(body.project_path, server_id, config)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/mcp/servers/{server_id}/resources/read")
async def mcp_read_resource(server_id: str, body: MCPResourceReadRequest) -> Any:
    config = load_config(CONFIG_PATH)
    try:
        return await read_server_resource(body.project_path, server_id, body.uri, config)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/mcp/servers/{server_id}/prompts")
async def mcp_list_prompts(server_id: str, body: MCPProjectRequest) -> Any:
    config = load_config(CONFIG_PATH)
    try:
        return await list_server_prompts(body.project_path, server_id, config)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/mcp/servers/{server_id}/prompts/{prompt_name}")
async def mcp_get_prompt(server_id: str, prompt_name: str, body: MCPPromptRequest) -> Any:
    config = load_config(CONFIG_PATH)
    try:
        return await get_server_prompt(body.project_path, server_id, prompt_name, body.arguments, config)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/mcp/servers/{server_id}/tools/{tool_name}/call")
async def mcp_call_tool(server_id: str, tool_name: str, body: MCPToolCallRequest) -> Any:
    config = load_config(CONFIG_PATH)
    server = next((item for item in config.mcp_servers if item.id == server_id), None)
    if server is None:
        raise HTTPException(status_code=404, detail=f"Unknown MCP server: {server_id}")
    if tool_name in server.requires_approval_for_tools and not body.approved_mutation:
        raise HTTPException(
            status_code=409,
            detail=(
                f"MCP tool {server_id}/{tool_name} is marked mutating and requires explicit human approval "
                "before it can be called. Create and approve an MCP approval artifact first."
            ),
        )
    try:
        return await call_server_tool(body.project_path, server_id, tool_name, body.arguments, config)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/mcp/approvals")
async def list_mcp_approvals(project_path: str | None = None) -> list[dict[str, Any]]:
    records = (
        mcp_approval_repository.list_for_project(project_path)
        if project_path
        else mcp_approval_repository.list_all_sorted()
    )
    return [record.model_dump() for record in records]


@router.post("/mcp/approvals")
async def create_mcp_approval_request(body: MCPApprovalCreateRequest) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    try:
        server = get_server_for_project(body.project_path, body.server_id, config)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if body.tool_name not in server.requires_approval_for_tools:
        raise HTTPException(
            status_code=400,
            detail=f"MCP tool {body.server_id}/{body.tool_name} is not configured as approval-gated",
        )
    record = create_mcp_approval(
        project_path=body.project_path,
        server_id=body.server_id,
        tool_name=body.tool_name,
        arguments=body.arguments,
        notes=body.notes,
    )
    return record.model_dump()


@router.post("/mcp/approvals/{approval_id}/approve")
async def approve_mcp_approval_request(approval_id: str, body: NotesRequest) -> dict[str, Any]:
    record = mcp_approval_repository.get(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="MCP approval request not found")
    if record.status != "pending":
        raise HTTPException(status_code=400, detail=f"MCP approval request is not pending: {record.status}")
    return approve_mcp_request(record, body.notes).model_dump()


@router.post("/mcp/approvals/{approval_id}/reject")
async def reject_mcp_approval_request(approval_id: str, body: NotesRequest) -> dict[str, Any]:
    record = mcp_approval_repository.get(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="MCP approval request not found")
    if record.status != "pending":
        raise HTTPException(status_code=400, detail=f"MCP approval request is not pending: {record.status}")
    return reject_mcp_request(record, body.notes).model_dump()


@router.post("/mcp/approvals/{approval_id}/execute")
async def execute_mcp_approval_request(approval_id: str) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    record = mcp_approval_repository.get(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="MCP approval request not found")
    if record.status != "approved":
        raise HTTPException(status_code=400, detail=f"MCP approval request is not approved: {record.status}")
    try:
        updated, result = await execute_approved_mcp_request(record, config)
        return {"approval": updated.model_dump(), "result": result}
    except Exception as exc:
        failed = fail_mcp_request(record, str(exc))
        raise HTTPException(
            status_code=502,
            detail={
                "message": str(exc),
                "approval": failed.model_dump(),
            },
        ) from exc
