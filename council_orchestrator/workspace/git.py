"""Git worktree helpers."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def sanitize_branch_component(raw: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "-", raw)
    safe = re.sub(r"-+", "-", safe).strip("-")
    return safe[:60] or "council-task"


def sanitize_path_segment(raw: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "-", raw)
    safe = re.sub(r"-+", "-", safe).strip("-")
    return safe[:60] or "worktree"


def build_branch_name(task: str, prefix: str = "council") -> str:
    return f"{prefix}/{sanitize_branch_component(task)}"


def create_worktree(
    repo_path: str,
    branch_name: str,
    default_branch: str = "main",
    worktree_name: str | None = None,
) -> str:
    repo = Path(repo_path).expanduser().resolve()
    worktree_root = repo.parent / ".worktrees"
    worktree_root.mkdir(parents=True, exist_ok=True)

    path_segment = sanitize_path_segment(worktree_name or branch_name.split("/")[-1])
    worktree_path = worktree_root / path_segment

    subprocess.run(
        ["git", "fetch", "origin", "--quiet"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    base_ref = f"origin/{default_branch}"
    add_command = ["git", "worktree", "add", "-b", branch_name, str(worktree_path), base_ref]

    try:
        subprocess.run(add_command, cwd=repo, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ""
        if "already exists" not in stderr:
            raise RuntimeError(f"Failed to create worktree: {stderr or exc.stdout}") from exc

        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), base_ref],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            subprocess.run(
                ["git", "checkout", branch_name],
                cwd=worktree_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as checkout_exc:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                cwd=repo,
                check=False,
                capture_output=True,
                text=True,
            )
            raise RuntimeError(
                f"Failed to checkout branch {branch_name}: {checkout_exc.stderr or checkout_exc.stdout}"
            ) from checkout_exc

    return str(worktree_path)


def destroy_worktree(repo_path: str, worktree_path: str) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", worktree_path],
        cwd=Path(repo_path).expanduser().resolve(),
        capture_output=True,
        text=True,
        check=False,
    )
