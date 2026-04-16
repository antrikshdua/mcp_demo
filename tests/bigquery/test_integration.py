"""Integration tests against a real BigQuery project.

These tests require:
  - BIGQUERY_PROJECT_ID set to a real GCP project
  - BIGQUERY_LOCATION set (e.g. US)
  - Valid GCP credentials (gcloud auth application-default login OR GOOGLE_APPLICATION_CREDENTIALS)

Run with:
    pytest tests/bigquery/test_integration.py -m integration -v

Skip automatically when BIGQUERY_PROJECT_ID is not set.
"""

from __future__ import annotations

import os

import pytest

# All tests in this file are marked `integration` and skipped without project ID
pytestmark = pytest.mark.integration


def _require_project() -> str:
    project = os.getenv("BIGQUERY_PROJECT_ID", "")
    if not project:
        pytest.skip("BIGQUERY_PROJECT_ID not set — skipping integration tests")
    return project


@pytest.fixture(scope="module")
def bq_db():
    """Create a real BigQueryDatabase using env config."""
    from bigquery.config import get_bigquery_config
    from bigquery.client import BigQueryDatabase

    cfg = get_bigquery_config()
    if cfg is None:
        pytest.skip("BIGQUERY_PROJECT_ID not set")
    cfg.check_auth_on_startup = False  # validate manually in test
    return BigQueryDatabase(cfg)


# ── Auth ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auth_validation():
    """Validate credentials against real GCP without starting server."""
    from bigquery.config import get_bigquery_config
    from bigquery.client import BigQueryDatabase
    from bigquery.auth import validate_authentication

    project = _require_project()
    cfg = get_bigquery_config()
    db = BigQueryDatabase(cfg)
    # Should not raise or sys.exit
    await validate_authentication(db.client, project, cfg.location)


# ── list_datasets ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_datasets_returns_results(bq_db):
    """list_datasets must return at least one dataset in a real project."""
    _require_project()
    result = await bq_db.list_datasets()
    assert result["success"] is True
    assert isinstance(result["data"], list)


@pytest.mark.asyncio
async def test_list_datasets_detailed(bq_db):
    """Detailed listing includes table_count and dataset_id keys."""
    _require_project()
    result = await bq_db.list_datasets(detailed=True, max_results=3)
    assert result["success"] is True
    if result["data"]:
        first = result["data"][0]
        assert "dataset_id" in first
        assert "table_count" in first


# ── run_query ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_simple_query(bq_db):
    """A trivial SELECT 1 should succeed."""
    _require_project()
    result = await bq_db.run_query("SELECT 1 AS n LIMIT 1")
    assert result["success"] is True
    assert result["total_count"] == 1


@pytest.mark.asyncio
async def test_dangerous_query_blocked(bq_db):
    """DROP TABLE must be rejected before hitting the network."""
    _require_project()
    result = await bq_db.run_query("DROP TABLE something")
    assert result["success"] is False
    assert "DROP" in result["error"]


@pytest.mark.asyncio
async def test_billing_cap_reported(bq_db):
    """max_bytes_billed must be present in a successful query response."""
    _require_project()
    result = await bq_db.run_query("SELECT 1 AS n LIMIT 1")
    assert result["success"] is True
    assert "max_bytes_billed" in result


# ── list_tables + get_table ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_tables_in_first_dataset(bq_db):
    """List tables in the first dataset found."""
    _require_project()
    ds_result = await bq_db.list_datasets(max_results=1)
    assert ds_result["success"] is True
    if not ds_result["data"]:
        pytest.skip("No datasets in project")
    dataset_id = ds_result["data"][0]
    result = await bq_db.list_tables(dataset_id)
    assert result["success"] is True
    assert "dataset_context" in result


@pytest.mark.asyncio
async def test_get_table_schema(bq_db):
    """get_table returns schema_with_fill_rates for the first table found."""
    _require_project()
    ds_result = await bq_db.list_datasets(max_results=1)
    assert ds_result["success"] is True
    if not ds_result["data"]:
        pytest.skip("No datasets in project")
    dataset_id = ds_result["data"][0]

    tables_result = await bq_db.list_tables(dataset_id, max_results=1)
    assert tables_result["success"] is True
    if not tables_result["data"]:
        pytest.skip("No tables in first dataset")
    table_id = tables_result["data"][0]

    result = await bq_db.get_table(dataset_id, table_id)
    assert result["success"] is True
    data = result["data"]
    assert "schema_with_fill_rates" in data
    assert "table_path" in data
    assert "type" in data
