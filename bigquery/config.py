"""BigQuery configuration — env var loading with typed dataclass."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class BigQueryConfig:
    # ── Required ──────────────────────────────────────────────────────────────
    project_id: str
    location: str = "US"

    # ── Auth ──────────────────────────────────────────────────────────────────
    # Path to service account JSON; None → use Application Default Credentials
    key_file: str | None = None

    # ── Startup Behaviour ─────────────────────────────────────────────────────
    check_auth_on_startup: bool = True

    # ── Access Control ────────────────────────────────────────────────────────
    # Empty list → all datasets allowed
    allowed_datasets: list[str] = field(default_factory=list)

    # ── Billing & Safety ─────────────────────────────────────────────────────
    # Default ~$0.50 USD per query at $5/TiB
    max_bytes_billed: int = 109_951_162_777
    timeout: int = 30  # query timeout in seconds

    # ── Result Limits ─────────────────────────────────────────────────────────
    max_results: int = 20
    list_max_results: int = 500
    list_max_results_detailed: int = 25

    # ── Table Analysis ────────────────────────────────────────────────────────
    sample_rows: int = 3
    sample_rows_for_stats: int = 500

    # ── Vector Search ─────────────────────────────────────────────────────────
    vector_search_enabled: bool = False
    embedding_model: str | None = None
    embedding_tables: list[str] = field(default_factory=list)
    embedding_column_contains: str = "embedding"
    distance_type: str = "COSINE"

    # ── Logging ───────────────────────────────────────────────────────────────
    # If set, BigQuery audit events are also written to this file path
    log_file: str | None = None


def _parse_bool(value: str, default: bool) -> bool:
    if not value:
        return default
    return value.strip().lower() in ("true", "1", "yes", "on")


def _parse_list(value: str) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def get_bigquery_config() -> BigQueryConfig | None:
    """Build BigQueryConfig from environment variables.

    Returns None if BIGQUERY_PROJECT_ID is not set (BigQuery disabled).
    """
    project_id = os.getenv("BIGQUERY_PROJECT_ID", "").strip()
    if not project_id:
        return None

    return BigQueryConfig(
        project_id=project_id,
        location=os.getenv("BIGQUERY_LOCATION", "US"),
        key_file=os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or None,
        check_auth_on_startup=_parse_bool(os.getenv("BIGQUERY_CHECK_AUTH_ON_STARTUP", "true"), default=True),
        allowed_datasets=_parse_list(os.getenv("BIGQUERY_ALLOWED_DATASETS", "")),
        max_bytes_billed=int(os.getenv("BIGQUERY_MAX_BYTES_BILLED", "109951162777")),
        timeout=int(os.getenv("BIGQUERY_TIMEOUT", "30")),
        max_results=int(os.getenv("BIGQUERY_MAX_RESULTS", "20")),
        list_max_results=int(os.getenv("BIGQUERY_LIST_MAX_RESULTS", "500")),
        list_max_results_detailed=int(os.getenv("BIGQUERY_LIST_MAX_RESULTS_DETAILED", "25")),
        sample_rows=int(os.getenv("BIGQUERY_SAMPLE_ROWS", "3")),
        sample_rows_for_stats=int(os.getenv("BIGQUERY_SAMPLE_ROWS_FOR_STATS", "500")),
        vector_search_enabled=_parse_bool(os.getenv("BIGQUERY_VECTOR_SEARCH_ENABLED", "false"), default=False),
        embedding_model=os.getenv("BIGQUERY_EMBEDDING_MODEL") or None,
        embedding_tables=_parse_list(os.getenv("BIGQUERY_EMBEDDING_TABLES", "")),
        embedding_column_contains=os.getenv("BIGQUERY_EMBEDDING_COLUMN_CONTAINS", "embedding"),
        distance_type=os.getenv("BIGQUERY_DISTANCE_TYPE", "COSINE").upper(),
        log_file=os.getenv("BIGQUERY_LOG_FILE") or None,
    )
