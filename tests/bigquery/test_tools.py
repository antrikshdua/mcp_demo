"""Unit tests for BigQueryDatabase — all BigQuery API calls are mocked.

No GCP credentials or network access required.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bigquery.config import BigQueryConfig
from bigquery.client import BigQueryDatabase, _success, _error


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def cfg() -> BigQueryConfig:
    return BigQueryConfig(
        project_id="test-project",
        location="US",
        check_auth_on_startup=False,
    )


@pytest.fixture
def db(cfg: BigQueryConfig) -> BigQueryDatabase:
    with patch("bigquery.client.create_bigquery_client") as mock_factory:
        mock_factory.return_value = MagicMock()
        database = BigQueryDatabase(cfg)
    return database


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_row(**kwargs: Any) -> MagicMock:
    row = MagicMock()
    row.__iter__ = lambda self: iter(kwargs.items())
    return row


def _make_query_job(rows: list[dict], total_bytes: int = 1_000) -> MagicMock:
    job = MagicMock()
    result_obj = MagicMock()
    result_obj.__iter__ = lambda self: iter([_make_row(**r) for r in rows])
    result_obj.total_rows = len(rows)
    job.result.return_value = result_obj
    job.total_bytes_processed = total_bytes
    return job


# ── run_query ──────────────────────────────────────────────────────────────────

class TestRunQuery:
    @pytest.mark.asyncio
    async def test_safe_query_executes(self, db: BigQueryDatabase):
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        db.client.query.return_value = _make_query_job(rows)
        result = await db.run_query("SELECT id, name FROM users LIMIT 10")
        assert result["success"] is True
        assert result["total_count"] == 2

    @pytest.mark.asyncio
    async def test_unsafe_query_rejected(self, db: BigQueryDatabase):
        result = await db.run_query("DROP TABLE users")
        assert result["success"] is False
        assert "DROP" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_query_rejected(self, db: BigQueryDatabase):
        result = await db.run_query("")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_rejected(self, db: BigQueryDatabase):
        result = await db.run_query("DELETE FROM users WHERE id = 1")
        assert result["success"] is False
        assert "DELETE" in result["error"]

    @pytest.mark.asyncio
    async def test_bytes_processed_returned(self, db: BigQueryDatabase):
        db.client.query.return_value = _make_query_job([{"n": 1}], total_bytes=50_000)
        result = await db.run_query("SELECT 1 AS n LIMIT 1")
        assert result.get("bytes_processed") == 50_000


# ── list_datasets ──────────────────────────────────────────────────────────────

class TestListDatasets:
    def _make_dataset(self, dataset_id: str) -> MagicMock:
        ds = MagicMock()
        ds.dataset_id = dataset_id
        return ds

    @pytest.mark.asyncio
    async def test_returns_sorted_names(self, db: BigQueryDatabase):
        db.client.list_datasets.return_value = [
            self._make_dataset("zebra"),
            self._make_dataset("alpha"),
        ]
        result = await db.list_datasets()
        assert result["success"] is True
        assert result["data"] == ["alpha", "zebra"]

    @pytest.mark.asyncio
    async def test_search_filter(self, db: BigQueryDatabase):
        db.client.list_datasets.return_value = [
            self._make_dataset("analytics"),
            self._make_dataset("raw_logs"),
        ]
        result = await db.list_datasets(search="analyt")
        assert result["success"] is True
        assert "analytics" in result["data"]
        assert "raw_logs" not in result["data"]

    @pytest.mark.asyncio
    async def test_allowed_datasets_enforced(self, cfg: BigQueryConfig):
        cfg.allowed_datasets = ["allowed_ds"]
        with patch("bigquery.client.create_bigquery_client") as mock_factory:
            mock_factory.return_value = MagicMock()
            db = BigQueryDatabase(cfg)
        db.client.list_datasets.return_value = [
            MagicMock(dataset_id="allowed_ds"),
            MagicMock(dataset_id="secret_ds"),
        ]
        result = await db.list_datasets()
        assert result["success"] is True
        assert "secret_ds" not in result["data"]
        assert "allowed_ds" in result["data"]


# ── list_tables ────────────────────────────────────────────────────────────────

class TestListTables:
    def _make_table(self, table_id: str) -> MagicMock:
        t = MagicMock()
        t.table_id = table_id
        t.table_type = "TABLE"
        t.time_partitioning = None
        t.range_partitioning = None
        return t

    @pytest.mark.asyncio
    async def test_denied_dataset_returns_error(self, cfg: BigQueryConfig):
        cfg.allowed_datasets = ["allowed_ds"]
        with patch("bigquery.client.create_bigquery_client") as mock_factory:
            mock_factory.return_value = MagicMock()
            db = BigQueryDatabase(cfg)
        result = await db.list_tables("secret_ds")
        assert result["success"] is False
        assert "not allowed" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_sorted_table_names(self, db: BigQueryDatabase):
        ds_obj = MagicMock()
        ds_obj.description = None
        ds_obj.location = "US"
        db.client.get_dataset.return_value = ds_obj
        db.client.list_tables.return_value = [
            self._make_table("zebra_table"),
            self._make_table("alpha_table"),
        ]
        result = await db.list_tables("my_dataset")
        assert result["success"] is True
        assert result["data"] == ["alpha_table", "zebra_table"]


# ── helper functions ────────────────────────────────────────────────────────────

class TestHelpers:
    def test_success_response(self):
        r = _success([1, 2, 3], total_count=3)
        assert r["success"] is True
        assert r["data"] == [1, 2, 3]
        assert r["total_count"] == 3

    def test_error_response(self):
        r = _error(ValueError("bad input"))
        assert r["success"] is False
        assert "bad input" in r["error"]
        assert r["error_type"] == "ValueError"
