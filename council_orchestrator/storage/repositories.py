"""File-backed repositories for runs, tasks, approvals, attempts, and QA reports."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, TypeVar

from pydantic import BaseModel

from ..schemas import (
    ApprovalRecord,
    ExecutionAttempt,
    MCPApprovalRecord,
    QAReport,
    RunRecord,
    TaskAssignment,
    TaskRecord,
)

DATA_ROOT = Path("data")

T = TypeVar("T", bound=BaseModel)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class FileRepository:
    model_type: type[T]

    def __init__(self, directory: Path, model_type: type[T]) -> None:
        self.directory = directory
        self.model_type = model_type
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, entity_id: str) -> Path:
        return self.directory / f"{entity_id}.json"

    def save(self, model: T) -> T:
        self.directory.mkdir(parents=True, exist_ok=True)
        self._path(model.id).write_text(
            json.dumps(model.model_dump(), indent=2, default=str),
            encoding="utf-8",
        )
        return model

    def get(self, entity_id: str) -> T | None:
        path = self._path(entity_id)
        if not path.exists():
            return None
        return self.model_type.model_validate_json(path.read_text(encoding="utf-8"))

    def list_all(self) -> list[T]:
        self.directory.mkdir(parents=True, exist_ok=True)
        items: list[T] = []
        for path in self.directory.glob("*.json"):
            try:
                items.append(self.model_type.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return items


class RunRepository(FileRepository):
    def __init__(self) -> None:
        super().__init__(DATA_ROOT / "runs", RunRecord)


class TaskRepository(FileRepository):
    def __init__(self) -> None:
        super().__init__(DATA_ROOT / "tasks", TaskRecord)

    def list_for_run(self, run_id: str) -> list[TaskRecord]:
        items = [task for task in self.list_all() if task.run_id == run_id]
        items.sort(key=lambda task: task.created_at)
        return items


class ApprovalRepository(FileRepository):
    def __init__(self) -> None:
        super().__init__(DATA_ROOT / "approvals", ApprovalRecord)

    def list_for_run(self, run_id: str) -> list[ApprovalRecord]:
        items = [record for record in self.list_all() if record.run_id == run_id]
        items.sort(key=lambda record: record.created_at)
        return items

    def list_for_task(self, task_id: str) -> list[ApprovalRecord]:
        items = [record for record in self.list_all() if record.task_id == task_id]
        items.sort(key=lambda record: record.created_at)
        return items


class TaskAssignmentRepository(FileRepository):
    def __init__(self) -> None:
        super().__init__(DATA_ROOT / "assignments", TaskAssignment)

    def list_for_run(self, run_id: str) -> list[TaskAssignment]:
        items = [record for record in self.list_all() if record.run_id == run_id]
        items.sort(key=lambda record: record.assigned_at)
        return items

    def list_for_task(self, task_id: str) -> list[TaskAssignment]:
        items = [record for record in self.list_all() if record.task_id == task_id]
        items.sort(key=lambda record: record.assigned_at)
        return items


class ExecutionAttemptRepository(FileRepository):
    def __init__(self) -> None:
        super().__init__(DATA_ROOT / "attempts", ExecutionAttempt)

    def list_for_task(self, task_id: str) -> list[ExecutionAttempt]:
        items = [record for record in self.list_all() if record.task_id == task_id]
        items.sort(key=lambda record: record.attempt_no)
        return items

    def next_attempt_no(self, task_id: str) -> int:
        attempts = self.list_for_task(task_id)
        return (attempts[-1].attempt_no + 1) if attempts else 1


class QAReportRepository(FileRepository):
    def __init__(self) -> None:
        super().__init__(DATA_ROOT / "qa_reports", QAReport)

    def list_for_task(self, task_id: str) -> list[QAReport]:
        items = [record for record in self.list_all() if record.task_id == task_id]
        items.sort(key=lambda record: record.created_at)
        return items

    def latest_for_task(self, task_id: str) -> QAReport | None:
        reports = self.list_for_task(task_id)
        return reports[-1] if reports else None


class MCPApprovalRepository(FileRepository):
    def __init__(self) -> None:
        super().__init__(DATA_ROOT / "mcp_approvals", MCPApprovalRecord)

    def list_all_sorted(self) -> list[MCPApprovalRecord]:
        items = self.list_all()
        items.sort(key=lambda record: record.created_at, reverse=True)
        return items

    def list_for_project(self, project_path: str) -> list[MCPApprovalRecord]:
        items = [record for record in self.list_all() if record.project_path == project_path]
        items.sort(key=lambda record: record.created_at, reverse=True)
        return items


run_repository = RunRepository()
task_repository = TaskRepository()
approval_repository = ApprovalRepository()
assignment_repository = TaskAssignmentRepository()
attempt_repository = ExecutionAttemptRepository()
qa_report_repository = QAReportRepository()
mcp_approval_repository = MCPApprovalRepository()
