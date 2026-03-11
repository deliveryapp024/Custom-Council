"""Dual-server dev runner. Starts FastAPI backend and Next.js frontend.

On Windows, uses process groups / taskkill to ensure all child processes
(uvicorn workers, npm/node) are properly terminated when you Ctrl+C or
close the terminal window.
"""

import atexit
import subprocess
import sys
import os
import signal
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
WEB_DIR = ROOT / "web"

# Keep track globally so atexit can reference them
_procs: list[subprocess.Popen] = []


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill a process and all of its children (Windows-safe)."""
    try:
        if sys.platform == "win32":
            # taskkill /T kills the entire process tree
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            import signal as _sig
            os.killpg(os.getpgid(proc.pid), _sig.SIGTERM)
    except (ProcessLookupError, OSError, PermissionError):
        pass


def _cleanup() -> None:
    """atexit / signal handler: kill every child tree."""
    for proc in _procs:
        _kill_tree(proc)
    for proc in _procs:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def main():
    # Register cleanup so processes are killed even if the terminal is
    # closed without Ctrl+C (e.g. clicking the X button).
    atexit.register(_cleanup)

    # On Windows, also handle CTRL_CLOSE_EVENT / CTRL_BREAK_EVENT
    if sys.platform == "win32":
        try:
            signal.signal(signal.SIGBREAK, lambda *_: (_cleanup(), sys.exit(0)))
        except (OSError, ValueError):
            pass

    popen_kwargs: dict = {}
    if sys.platform != "win32":
        popen_kwargs["preexec_fn"] = os.setsid

    # ── Start FastAPI backend on :8000 ──
    print("🚀  Starting FastAPI backend on http://localhost:8000 ...")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "council_orchestrator.api.app:app",
         "--reload", "--port", "8000"],
        cwd=str(ROOT),
        **popen_kwargs,
    )
    _procs.append(backend)

    # ── Start Next.js frontend on :3000 ──
    if WEB_DIR.exists():
        print("🌐  Starting Next.js frontend on http://localhost:3000 ...")
        frontend = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(WEB_DIR),
            shell=True,
            **popen_kwargs,
        )
        _procs.append(frontend)
    else:
        print(f"⚠️  {WEB_DIR} not found — skipping frontend.")

    print("\n✅  Both servers running. Press Ctrl+C to stop.\n")

    import time
    try:
        # Wait for any process to exit
        while True:
            for proc in _procs:
                if proc.poll() is not None:
                    # A process stopped (e.g., backend triggered shutdown)
                    raise KeyboardInterrupt()
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n🛑  Shutting down all servers...")
        _cleanup()
        print("Done.")


if __name__ == "__main__":
    main()
