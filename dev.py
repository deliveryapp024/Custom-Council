"""Dual-server dev runner. Starts FastAPI backend and Next.js frontend."""

import subprocess
import sys
import os
import signal
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
WEB_DIR = ROOT / "web"


def main():
    procs = []
    try:
        # Start FastAPI backend on :8000
        print("🚀  Starting FastAPI backend on http://localhost:8000 ...")
        backend = subprocess.Popen(
            [sys.executable, "-m", "uvicorn",
             "council_orchestrator.api.app:app",
             "--reload", "--port", "8000"],
            cwd=str(ROOT),
        )
        procs.append(backend)

        # Start Next.js frontend on :3000
        if WEB_DIR.exists():
            print("🌐  Starting Next.js frontend on http://localhost:3000 ...")
            frontend = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=str(WEB_DIR),
                shell=True,
            )
            procs.append(frontend)
        else:
            print(f"⚠️  {WEB_DIR} not found — skipping frontend.")

        print("\n✅  Both servers running. Press Ctrl+C to stop.\n")

        # Wait for any process to exit
        for proc in procs:
            proc.wait()

    except KeyboardInterrupt:
        print("\n🛑  Shutting down...")
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=5)
        print("Done.")


if __name__ == "__main__":
    main()
