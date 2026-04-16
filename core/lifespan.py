"""
Application state and lifespan management.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from fastmcp import FastMCP

from schemas.models import NoteResult

if TYPE_CHECKING:
    from bigquery.client import BigQueryDatabase


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
    # BigQuery — None when BIGQUERY_PROJECT_ID is not set (disabled gracefully)
    bigquery_db: "BigQueryDatabase | None" = None


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

    # ── BigQuery (optional) ───────────────────────────────────────────────────
    bigquery_db = None
    try:
        from bigquery.config import get_bigquery_config
        bq_cfg = get_bigquery_config()
        if bq_cfg is not None:
            from bigquery.client import BigQueryDatabase
            from bigquery.auth import validate_authentication
            bigquery_db = BigQueryDatabase(bq_cfg)
            if bq_cfg.check_auth_on_startup:
                await validate_authentication(
                    bigquery_db.client, bq_cfg.project_id, bq_cfg.location
                )
            print(f"[lifespan] BigQuery enabled (project={bq_cfg.project_id})")
        else:
            print("[lifespan] BigQuery disabled (BIGQUERY_PROJECT_ID not set)")
    except ImportError:
        print("[lifespan] BigQuery disabled (google-cloud-bigquery not installed)")

    state = AppState(http_client=http_client, bigquery_db=bigquery_db)

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
