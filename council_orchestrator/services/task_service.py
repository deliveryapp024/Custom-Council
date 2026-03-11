"""Task generation and routing helpers."""

from __future__ import annotations

import json
from typing import Any

from ..engines import get_engine
from ..skill_catalog import agent_skill_ids
from ..schemas import AgentProfile, AppConfig, SkillDefinition, TaskRecord
from ..storage.repositories import new_id, task_repository, utc_now_iso


def _task_generation_prompt(plan: str, config: AppConfig) -> str:
    agents = "\n".join(f"- {agent.id}: {agent.display_name}" for agent in config.agents)
    skills = "\n".join(f"- {skill.id}: {skill.name}" for skill in config.skills)
    return f"""You are converting an approved implementation plan into a small task list.

Approved plan:
{plan}

Available agents:
{agents}

Available skills:
{skills}

Return strict JSON only in this shape:
{{
  "tasks": [
    {{
      "title": "short title",
      "description": "what to do",
      "priority": 3,
      "depends_on": [],
      "recommended_agent_id": "agent-id-or-empty",
      "recommended_skills": ["skill-id"],
      "routing_reason": "one sentence"
    }}
  ]
}}

Rules:
- Generate at most {config.task_generation.max_tasks} tasks
- Only use skill ids from the provided catalog
- Only use agent ids from the provided catalog
- Prefer sequential work
"""


async def generate_tasks_for_run(run, config: AppConfig) -> list[TaskRecord]:
    prompt = _task_generation_prompt(run.chairman_output, config)
    engine = get_engine(config.chairman.engine)
    response = await engine.generate(
        prompt,
        model=config.chairman.model,
        member_name=config.chairman.name,
        timeout=config.chairman.timeout_seconds,
    )
    if not response.ok:
        return _fallback_tasks(run, config)

    parsed = _parse_task_payload(response.text)
    if not parsed:
        return _fallback_tasks(run, config)

    created_at = utc_now_iso()
    tasks: list[TaskRecord] = []
    for item in parsed[: config.task_generation.max_tasks]:
        recommended_skills = [
            skill_id for skill_id in item.get("recommended_skills", []) if _skill_exists(skill_id, config.skills)
        ]
        recommended_agent_id = item.get("recommended_agent_id") or None
        if recommended_agent_id and not _agent_exists(recommended_agent_id, config.agents):
            recommended_agent_id = None
        if recommended_agent_id is None:
            recommended_agent_id = recommend_agent(recommended_skills, config.agents, "execute", config)

        tasks.append(
            TaskRecord(
                id=new_id("task"),
                run_id=run.id,
                title=item.get("title", "Implementation Task"),
                description=item.get("description", run.chairman_output),
                priority=int(item.get("priority", 3)),
                depends_on=[str(dep) for dep in item.get("depends_on", [])],
                recommended_agent_id=recommended_agent_id,
                recommended_skills=recommended_skills,
                routing_reason=item.get("routing_reason") or _build_routing_reason(recommended_agent_id, recommended_skills),
                created_at=created_at,
                updated_at=created_at,
            )
        )

    if not tasks:
        return _fallback_tasks(run, config)

    for task in tasks:
        task_repository.save(task)
    return tasks


def recommend_agent(
    skill_ids: list[str],
    agents: list[AgentProfile],
    workflow: str,
    config: AppConfig,
) -> str | None:
    candidates = [agent for agent in agents if workflow in agent.allowed_workflows]
    if not candidates:
        return None

    scored = []
    for agent in candidates:
        enabled_skills = agent_skill_ids(agent, config)
        score = sum(1 for skill in skill_ids if skill in enabled_skills)
        scored.append((score, agent.display_name, agent.id))
    scored.sort(reverse=True)
    best = scored[0]
    return best[2]


def assign_task(
    task: TaskRecord,
    agent_id: str,
    selected_skills: list[str] | None = None,
) -> TaskRecord:
    task.selected_agent_id = agent_id
    task.selected_skills = selected_skills or task.recommended_skills[:]
    task.status = "awaiting_execution_approval"
    task.updated_at = utc_now_iso()
    return task_repository.save(task)


def _parse_task_payload(raw: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict) and isinstance(payload.get("tasks"), list):
            return [item for item in payload["tasks"] if isinstance(item, dict)]
    except json.JSONDecodeError:
        pass
    return []


def _fallback_tasks(run, config: AppConfig) -> list[TaskRecord]:
    created_at = utc_now_iso()
    task = TaskRecord(
        id=new_id("task"),
        run_id=run.id,
        title="Implement approved plan",
        description=run.chairman_output,
        priority=3,
        recommended_agent_id=recommend_agent([], config.agents, "execute", config),
        recommended_skills=[],
        routing_reason="Fallback single task generated from approved plan.",
        created_at=created_at,
        updated_at=created_at,
    )
    task_repository.save(task)
    return [task]


def _skill_exists(skill_id: str, skills: list[SkillDefinition]) -> bool:
    return any(skill.id == skill_id for skill in skills)


def _agent_exists(agent_id: str, agents: list[AgentProfile]) -> bool:
    return any(agent.id == agent_id for agent in agents)


def _build_routing_reason(agent_id: str | None, skills: list[str]) -> str:
    if agent_id and skills:
        return f"Matched agent {agent_id} to skills: {', '.join(skills)}."
    if agent_id:
        return f"Defaulted to agent {agent_id}."
    return "No matching agent recommendation available."
