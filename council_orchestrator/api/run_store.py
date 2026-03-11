"""API-facing storage helpers built on repository-style file storage."""

from __future__ import annotations

from typing import Any

from ..schemas import RunRecord
from ..storage.repositories import (
    approval_repository,
    assignment_repository,
    attempt_repository,
    new_id,
    qa_report_repository,
    run_repository,
    task_repository,
    utc_now_iso,
)


def new_run(task: str, project_path: str) -> dict[str, Any]:
    run = RunRecord(
        id=new_id("run"),
        task=task,
        project_path=project_path,
        created_at=utc_now_iso(),
        status="created",
    )
    run_repository.save(run)
    return hydrate_run(run.id) or run.model_dump()


def save_run(run: dict[str, Any]) -> None:
    run_repository.save(RunRecord.model_validate(run))


def load_run(run_id: str) -> dict[str, Any] | None:
    return hydrate_run(run_id)


def hydrate_run(run_id: str) -> dict[str, Any] | None:
    run = run_repository.get(run_id)
    if run is None:
        return None
    tasks = task_repository.list_for_run(run_id)
    approvals = approval_repository.list_for_run(run_id)
    assignments = assignment_repository.list_for_run(run_id)

    payload = run.model_dump()
    payload["tasks"] = [task.model_dump() for task in tasks]
    payload["approvals"] = [record.model_dump() for record in approvals]
    payload["assignments"] = [record.model_dump() for record in assignments]

    for task in payload["tasks"]:
        task_id = task["id"]
        task["assignments"] = [item.model_dump() for item in assignment_repository.list_for_task(task_id)]
        task["attempts"] = [item.model_dump() for item in attempt_repository.list_for_task(task_id)]
        task["qa_reports"] = [item.model_dump() for item in qa_report_repository.list_for_task(task_id)]
        task["approvals"] = [
            record.model_dump()
            for record in approvals
            if record.task_id == task_id
        ]

    return payload


def list_runs() -> list[dict[str, Any]]:
    runs = []
    for run in run_repository.list_all():
        tasks = task_repository.list_for_run(run.id)
        stage1_results = run.stage1_results
        runs.append(
            {
                "id": run.id,
                "task": run.task,
                "status": run.status,
                "created_at": run.created_at,
                "duration_ms": run.duration_ms,
                "members_ok": sum(1 for result in stage1_results if result.ok),
                "members_total": len(stage1_results),
                "task_count": len(tasks),
                "completed_tasks": sum(1 for task in tasks if task.status == "completed"),
            }
        )
    runs.sort(key=lambda item: item["created_at"], reverse=True)
    return runs
