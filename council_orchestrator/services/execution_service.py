"""Execution workflow helpers."""

from __future__ import annotations

from pathlib import Path

from ..executor import get_executor
from ..schemas import AppConfig, ExecutionAttempt, RunRecord, TaskRecord
from ..storage.repositories import attempt_repository, run_repository, task_repository, new_id, utc_now_iso
from ..testing.runner import run_test_loop
from ..workspace.git import build_branch_name, create_worktree, sanitize_path_segment


def build_execution_prompt(task: TaskRecord, run: RunRecord, config: AppConfig) -> str:
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

    skill_block = "\n".join(skill_prompts)
    return f"""Task title: {task.title}

Task description:
{task.description}

Overall approved plan:
{run.chairman_output}

Selected skills:
{skill_block or "No additional skills selected."}

Work only on this task. Do not close the task yourself. Stop after implementation.
"""


def execute_task(task: TaskRecord, run: RunRecord, config: AppConfig) -> ExecutionAttempt:
    executor_config = config.executor.model_copy()
    if task.selected_agent_id:
        matching_agent = next((agent for agent in config.agents if agent.id == task.selected_agent_id), None)
        if matching_agent is not None:
            executor_config.agent = matching_agent.executor_type
            executor_config.model = matching_agent.model_override or executor_config.model

    executor = get_executor(executor_config)

    if not run.workspace_path or not Path(run.workspace_path).exists():
        branch_name = run.branch_name or build_branch_name(run.task[:30])
        worktree_name = sanitize_path_segment(run.task[:30])
        run.workspace_path = create_worktree(
            run.project_path,
            branch_name,
            default_branch=config.project.default_branch,
            worktree_name=worktree_name,
        )
        run.branch_name = branch_name
        run_repository.save(run)

    prompt = build_execution_prompt(task, run, config)
    started_at = utc_now_iso()
    attempt = ExecutionAttempt(
        id=new_id("attempt"),
        task_id=task.id,
        run_id=run.id,
        attempt_no=attempt_repository.next_attempt_no(task.id),
        agent_id=task.selected_agent_id or executor_config.agent,
        prompt=prompt,
        started_at=started_at,
    )
    attempt_repository.save(attempt)

    result = executor.run_plan(run.workspace_path, prompt)
    attempt.finished_at = utc_now_iso()
    attempt.exit_code = result.exit_code
    attempt.stdout = result.stdout
    attempt.stderr = result.stderr
    attempt.logs_path = result.logs_path

    if result.exit_code == 0:
        passed = run_test_loop(
            run.workspace_path,
            config.executor.test_command,
            executor,
            config.executor.max_retries,
        )
        attempt.test_result = "passed" if passed else "failed"
        task.status = "qa_review" if passed else "execution_retry_needed"
    else:
        attempt.test_result = "not_run"
        task.status = "execution_retry_needed"

    attempt_repository.save(attempt)
    task.latest_attempt_id = attempt.id
    task.worktree_path = run.workspace_path
    task.branch_name = run.branch_name
    task.updated_at = utc_now_iso()
    task_repository.save(task)
    return attempt
