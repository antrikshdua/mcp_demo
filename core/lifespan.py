"""
Application state and lifespan management.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from fastmcp import FastMCP

from schemas.models import NoteResult


@dataclass
class AppState:
    """
    Holds long-lived resources created once at startup.
    In production: asyncpg pool, Redis client, loaded ML model, etc.
    Here we use in-memory fakes so no external services are required.
    """
    http_client: httpx.AsyncClient
    notes_db: dict[str, NoteResult] = field(default_factory=dict)
    request_count: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """
    Create shared resources before the server accepts requests,
    then clean them up on shutdown.
    """
    print("[lifespan] Starting up -- creating shared resources...")

    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        headers={"User-Agent": "FastMCP-ProductionServer/1.0"},
        follow_redirects=True,
    )

    state = AppState(http_client=http_client)

    # Seed some demo data
    seed_notes = [
        NoteResult(
            id="1", title="Welcome", body="Hello from FastMCP!",
            tags=["intro"], created_at="2026-01-01T00:00:00Z",
        ),
        NoteResult(
            id="2", title="Deploy Guide", body="Use Docker + nginx for production.",
            tags=["ops", "docker"], created_at="2026-01-02T00:00:00Z",
        ),
        NoteResult(
            id="3", title="MCP Tips", body="Always mask error details in prod.",
            tags=["mcp", "security"], created_at="2026-01-03T00:00:00Z",
        ),
    ]
    for note in seed_notes:
        state.notes_db[note.id] = note

    print("[lifespan] Ready -- seeded 3 demo notes, HTTP client created.")

    try:
        yield state
    finally:
        print("[lifespan] Shutting down -- releasing resources...")
        await http_client.aclose()
        print("[lifespan] Shutdown complete.")
