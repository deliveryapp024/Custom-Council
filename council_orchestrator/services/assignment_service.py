"""Task assignment helpers."""

from __future__ import annotations

from ..skill_catalog import agent_skill_ids
from ..schemas import AppConfig, TaskAssignment, TaskRecord
from ..storage.repositories import (
    assignment_repository,
    new_id,
    task_repository,
    utc_now_iso,
)


def create_assignment(
    task: TaskRecord,
    agent_id: str,
    selected_skills: list[str],
    config: AppConfig,
    notes: str = "",
) -> TaskAssignment:
    agent = next((candidate for candidate in config.agents if candidate.id == agent_id), None)
    if agent is None:
        raise ValueError(f"Unknown agent: {agent_id}")

    allowed_skill_ids = agent_skill_ids(agent, config)
    unknown_skills = [skill_id for skill_id in selected_skills if skill_id not in allowed_skill_ids]
    if unknown_skills:
        raise ValueError(
            f"Agent {agent_id} does not have the requested skills: {', '.join(sorted(unknown_skills))}"
        )

    assigned_at = utc_now_iso()
    assignment = TaskAssignment(
        id=new_id("assign"),
        task_id=task.id,
        run_id=task.run_id,
        agent_id=agent_id,
        selected_skills=selected_skills,
        assigned_at=assigned_at,
        notes=notes,
    )
    assignment_repository.save(assignment)

    task.selected_agent_id = agent_id
    task.selected_skills = selected_skills
    task.status = "awaiting_execution_approval"
    task.updated_at = assigned_at
    task_repository.save(task)
    return assignment
