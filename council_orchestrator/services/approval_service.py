"""Approval lifecycle helpers."""

from __future__ import annotations

from ..schemas import ApprovalRecord, RunRecord, TaskRecord
from ..storage.repositories import approval_repository, new_id, run_repository, task_repository, utc_now_iso


def record_plan_approval(run: RunRecord, decision: str, notes: str = "") -> ApprovalRecord:
    record = ApprovalRecord(
        id=new_id("approval"),
        gate="plan",
        decision=decision,
        run_id=run.id,
        notes=notes,
        created_at=utc_now_iso(),
    )
    approval_repository.save(record)
    run.status = "plan_approved" if decision == "approved" else "rejected"
    run_repository.save(run)
    return record


def record_task_approval(task: TaskRecord, gate: str, decision: str, notes: str = "") -> ApprovalRecord:
    record = ApprovalRecord(
        id=new_id("approval"),
        gate=gate,
        decision=decision,
        run_id=task.run_id,
        task_id=task.id,
        notes=notes,
        created_at=utc_now_iso(),
    )
    approval_repository.save(record)

    if gate == "execution":
        task.status = "awaiting_execution_approval" if decision == "approved" else "rejected"
    elif gate == "completion":
        task.status = "completed" if decision == "approved" else "execution_retry_needed"

    task.updated_at = utc_now_iso()
    task_repository.save(task)
    return record
