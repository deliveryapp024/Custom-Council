"""Typer CLI entrypoint."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import typer

from .approval.gate import Approved, EditRequested, Rejected, request_approval
from .config import load_config
from .council.engine import run_stage1, run_stage2, run_stage3
from .executor import get_executor
from .testing.runner import run_test_loop
from .workspace.git import build_branch_name, create_worktree, sanitize_path_segment

app = typer.Typer(add_completion=False)


@app.command()
def run(
    task: str = typer.Option(..., "--task", "-t", help="The coding task to run through the council"),
    project_path: str = typer.Option(".", "--project-path", "-p", help="Path to the target Git repository"),
    config_path: str = typer.Option("config.yml", "--config-path", "-c", help="Path to config.yml"),
) -> None:
    """Run the full Council Orchestrator pipeline."""
    config = load_config(config_path)
    _preflight(config)
    asyncio.run(_run_pipeline(task, project_path, config))


async def _run_pipeline(task: str, project_path: str, config) -> None:
    run_dir = Path("data/runs") / sanitize_path_segment(task)
    run_dir.mkdir(parents=True, exist_ok=True)

    print("Phase 1: Gathering opinions from the council...")
    stage1 = await run_stage1(task, config)
    stage2, aggregate_rankings = await run_stage2(task, stage1, config)
    final_plan = await run_stage3(task, stage1, stage2, config)

    print("\nAggregate rankings:")
    for entry in aggregate_rankings:
        print(
            f"- {entry.member_name}: average rank {entry.average_rank} "
            f"across {entry.rankings_count} reviews"
        )

    while True:
        approval = request_approval(final_plan, run_dir)
        if isinstance(approval, Approved):
            print(f"Plan hash: {approval.plan_hash}")
            approved_plan_file = approval.plan_file
            break
        if isinstance(approval, Rejected):
            return
        if isinstance(approval, EditRequested):
            print("Re-running chairman with your feedback...")
            final_plan = await run_stage3(
                task,
                stage1,
                stage2,
                config,
                feedback=approval.feedback,
            )
            continue

    branch_name = build_branch_name(task[:30])
    worktree_name = sanitize_path_segment(task[:30])
    worktree = create_worktree(
        project_path,
        branch_name,
        default_branch=config.project.default_branch,
        worktree_name=worktree_name,
    )

    print(f"Phase 4: Executing approved plan from {approved_plan_file}...")
    executor = get_executor(config.executor)
    result = executor.run_plan(worktree, final_plan)
    if result.exit_code != 0:
        raise RuntimeError(
            f"Executor exited with code {result.exit_code}. Aborting before tests."
        )

    print("Phase 5: Running tests...")
    passed = run_test_loop(
        worktree,
        config.executor.test_command,
        executor,
        config.executor.max_retries,
    )

    if passed and config.executor.auto_commit:
        subprocess.run(["git", "add", "."], cwd=worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"council: {task}"],
            cwd=worktree,
            check=True,
        )
        print(f"Done. Changes committed on branch: {branch_name}")
        if config.executor.auto_push:
            subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=worktree, check=True)
            print("Branch pushed to origin.")
    elif not passed:
        print(f"Tests failed. Worktree preserved at: {worktree}")


def _preflight(config) -> None:
    planning_commands = set()
    for member in config.council_members:
        if member.enabled and member.engine == "opencode_cli":
            planning_commands.add("opencode")
    if config.chairman.engine == "opencode_cli":
        planning_commands.add("opencode")

    for command in planning_commands:
        if shutil.which(command) is None:
            raise RuntimeError(f"Required command not found on PATH: {command}")

    if config.executor.agent in {"opencode", "aider"}:
        command = config.executor.agent
        if shutil.which(command) is None:
            raise RuntimeError(f"Required command not found on PATH: {command}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
