"""QA workflow helpers."""

from __future__ import annotations

import json
from pathlib import Path

from ..engines import get_engine
from ..schemas import AppConfig, QAFinding, QAReport, RunRecord, TaskRecord
from ..storage.repositories import qa_report_repository, task_repository, new_id, utc_now_iso


def build_qa_prompt(task: TaskRecord, run: RunRecord, config: AppConfig) -> str:
    skill_prompts = []
    for skill in config.skills:
        if skill.id in task.selected_skills:
            mcp_lines = [
                f"- {action.type}: {action.server_id}/{action.name}{' [mutating]' if action.mutating else ''}"
                for action in skill.mcp_actions
            ]
            skill_prompts.append(
                "\n".join(
                    [
                        f"Skill: {skill.name} ({skill.id})",
                        f"Source: {skill.source or 'config'}",
                        f"Guidance summary: {skill.prompt_preamble or skill.description}",
                        f"MCP actions:\n{chr(10).join(mcp_lines) if mcp_lines else 'None'}",
                        f"Instructions:\n{skill.instructions or skill.prompt_preamble or skill.description}",
                    ]
                )
            )

    return f"""You are the dedicated QA reviewer for a coding task.

Task title: {task.title}
Task description:
{task.description}

Approved plan:
{run.chairman_output}

Selected skills:
{chr(10).join(skill_prompts) or "No extra skills selected."}

Return strict JSON:
{{
  "summary": "short summary",
  "recommendation": "pass" or "fail",
  "findings": [
    {{
      "title": "finding title",
      "severity": "critical|high|medium|low",
      "details": "why it matters",
      "suggested_fix": "optional fix"
    }}
  ]
}}
"""


async def run_qa(task: TaskRecord, run: RunRecord, config: AppConfig) -> QAReport:
    reviewer_id = config.qa.reviewer_agent_id or next(
        (agent.id for agent in config.agents if agent.qa_capable),
        None,
    )
    if reviewer_id is None:
        raise RuntimeError("No QA-capable agent configured")

    reviewer = next(agent for agent in config.agents if agent.id == reviewer_id)
    engine_name = "opencode_cli" if reviewer.executor_type == "opencode" else "litellm"
    engine = get_engine(engine_name)
    prompt = build_qa_prompt(task, run, config)
    response = await engine.generate(
        prompt,
        model=reviewer.model_override,
        member_name=reviewer.display_name,
        timeout=config.chairman.timeout_seconds,
    )

    report = _parse_qa_output(response.text, task, run, reviewer_id)
    blocking = {severity for severity in config.qa.blocking_severities}
    has_blocking = any(finding.severity in blocking for finding in report.findings)
    task.latest_qa_report_id = report.id
    task.status = "execution_retry_needed" if has_blocking or report.recommendation == "fail" else "awaiting_completion_approval"
    task.updated_at = utc_now_iso()
    task_repository.save(task)
    qa_report_repository.save(report)
    return report


def _parse_qa_output(raw: str, task: TaskRecord, run: RunRecord, agent_id: str) -> QAReport:
    created_at = utc_now_iso()
    try:
        payload = json.loads(raw)
        findings = [
            QAFinding(
                title=item.get("title", "Finding"),
                severity=item.get("severity", "medium"),
                details=item.get("details", ""),
                suggested_fix=item.get("suggested_fix", ""),
            )
            for item in payload.get("findings", [])
            if isinstance(item, dict)
        ]
        return QAReport(
            id=new_id("qa"),
            task_id=task.id,
            run_id=run.id,
            attempt_id=task.latest_attempt_id,
            agent_id=agent_id,
            summary=payload.get("summary", "QA report generated."),
            findings=findings,
            recommendation=payload.get("recommendation", "pass"),
            raw_output=raw,
            created_at=created_at,
        )
    except json.JSONDecodeError:
        return QAReport(
            id=new_id("qa"),
            task_id=task.id,
            run_id=run.id,
            attempt_id=task.latest_attempt_id,
            agent_id=agent_id,
            summary="Unstructured QA output received.",
            findings=[],
            recommendation="pass",
            raw_output=raw,
            created_at=created_at,
        )
