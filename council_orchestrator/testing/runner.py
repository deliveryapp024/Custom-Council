"""Test loop helpers."""

from __future__ import annotations

import subprocess

from ..executor.base import ExecutionAgent


def run_test_loop(
    workspace_path: str,
    test_command: list[str],
    executor: ExecutionAgent,
    max_retries: int = 3,
) -> bool:
    for attempt in range(1, max_retries + 1):
        print(f"\nTest attempt {attempt}/{max_retries}...")
        result = subprocess.run(
            test_command,
            cwd=workspace_path,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            print("All tests passed.")
            return True

        error_output = (result.stdout or "") + "\n" + (result.stderr or "")
        print(f"Tests failed on attempt {attempt}.")

        if attempt < max_retries:
            print("Sending failure output back to the executor.")
            fix_exit = executor.send_followup(workspace_path, error_output[-3000:])
            if fix_exit != 0:
                print(f"Executor fix attempt also failed with exit code {fix_exit}.")

    print("Max retries reached. Tests are still failing.")
    return False
