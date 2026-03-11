"""FastAPI application assembly."""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import load_config
from .routes import router

_start_time = time.monotonic()

app = FastAPI(
    title="Council Orchestrator API",
    description="REST + SSE API for the multi-model council orchestrator",
    version="0.2.0",
)

# Allow the Next.js dev server to talk to us
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def preload_config() -> None:
    load_config("config.yml")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/server/status")
async def server_status():
    uptime = int(time.monotonic() - _start_time)
    return {
        "status": "running",
        "uptime_seconds": uptime,
        "pid": os.getpid(),
    }


@app.post("/api/server/shutdown")
async def shutdown_server():
    """Gracefully stop the backend server.

    Sends SIGTERM (or equivalent on Windows) after a short delay so that
    the HTTP response has time to reach the client.
    """
    async def _delayed_exit():
        await asyncio.sleep(0.5)
        if sys.platform == "win32":
            os._exit(0)
        else:
            os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_delayed_exit())
    return {"status": "shutting_down", "message": "Server will stop in ~1 second."}
