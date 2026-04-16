"""BigQuery MCP sub-server — 5 tools for production BigQuery access."""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP

from schemas.models import (
    BigQueryQueryInput,
    DatasetListInput,
    TableGetInput,
    TableListInput,
    VectorSearchInput,
)

bigquery_mcp = FastMCP(
    "BigQuery",
    instructions=(
        "Tools for reading from Google BigQuery. "
        "Always include a LIMIT clause in SQL queries. "
        "Use bq_list_datasets → bq_list_tables → bq_get_table to explore before querying. "
        "Use bq_vector_search with empty query_text to discover embedding tables."
    ),
)


def _get_db(ctx: Context) -> Any:
    """Retrieve BigQueryDatabase from AppState, or raise if not configured."""
    db = ctx.request_context.lifespan_context.bigquery_db
    if db is None:
        raise RuntimeError(
            "BigQuery is not configured. Set BIGQUERY_PROJECT_ID (and BIGQUERY_LOCATION) "
            "in your environment and restart the server."
        )
    return db


# ── run_query ──────────────────────────────────────────────────────────────────

@bigquery_mcp.tool(tags={"read"})
async def bq_run_query(inp: BigQueryQueryInput, ctx: Context) -> dict[str, Any]:
    """Execute a read-only BigQuery SQL SELECT (or WITH/CTE) query.

    Safety guarantees:
    - Only SELECT and WITH statements are accepted; all DML/DDL is rejected.
    - SQL comments are stripped before validation to prevent bypass attempts.
    - Multi-statement scripts (semicolon-separated) are blocked.
    - A per-query billing cap is enforced (default ~$0.50 USD).

    Always include a LIMIT clause. Start with LIMIT 20 for exploration.
    """
    await ctx.info(f"[bq_run_query] executing query ({len(inp.query)} chars)")
    db = _get_db(ctx)
    result = await db.run_query(inp.query)
    if result.get("success"):
        count = result.get("total_count", 0)
        bytes_processed = result.get("bytes_processed") or 0
        await ctx.info(f"[bq_run_query] returned {count} rows, {bytes_processed:,} bytes scanned")
    return result


# ── list_datasets ──────────────────────────────────────────────────────────────

@bigquery_mcp.tool(tags={"read"})
async def bq_list_datasets(inp: DatasetListInput, ctx: Context) -> dict[str, Any]:
    """List all accessible BigQuery datasets in the configured project.

    Use detailed=true to include table counts and descriptions.
    Use search to filter by dataset name (case-insensitive substring match).
    Dataset allowlist (BIGQUERY_ALLOWED_DATASETS) is enforced automatically.
    """
    await ctx.info(f"[bq_list_datasets] search={inp.search!r} detailed={inp.detailed}")
    db = _get_db(ctx)
    return await db.list_datasets(
        search=inp.search,
        detailed=inp.detailed,
        max_results=inp.max_results,
    )


# ── list_tables ────────────────────────────────────────────────────────────────

@bigquery_mcp.tool(tags={"read"})
async def bq_list_tables(inp: TableListInput, ctx: Context) -> dict[str, Any]:
    """List tables in a BigQuery dataset with optional metadata.

    Returns dataset context (location, description, total table count) alongside
    the table list. Use detailed=true for row counts and storage size.
    """
    await ctx.info(f"[bq_list_tables] dataset={inp.dataset_id!r} search={inp.search!r} detailed={inp.detailed}")
    db = _get_db(ctx)
    return await db.list_tables(
        dataset_id=inp.dataset_id,
        search=inp.search,
        detailed=inp.detailed,
        max_results=inp.max_results,
    )


# ── get_table ──────────────────────────────────────────────────────────────────

@bigquery_mcp.tool(tags={"read"})
async def bq_get_table(inp: TableGetInput, ctx: Context) -> dict[str, Any]:
    """Get full table metadata: schema, column fill-rates, partition info, PKs, and sample rows.

    Schema includes fill_rate_percent per column (computed via row sampling).
    Sample rows are ordered by the first timestamp column (DESC) if one exists.
    Partition and primary-key constraints are surfaced when defined on the table.
    """
    await ctx.info(f"[bq_get_table] {inp.dataset_id}.{inp.table_id}")
    db = _get_db(ctx)
    await ctx.report_progress(progress=0, total=3)
    result = await db.get_table(inp.dataset_id, inp.table_id)
    await ctx.report_progress(progress=3, total=3)
    return result


# ── vector_search ──────────────────────────────────────────────────────────────

@bigquery_mcp.tool(tags={"read"})
async def bq_vector_search(inp: VectorSearchInput, ctx: Context) -> dict[str, Any]:
    """Semantic vector search over BigQuery embedding tables.

    Two modes:
    - Discovery (query_text empty): finds tables with embedding columns using
      INFORMATION_SCHEMA or the BIGQUERY_EMBEDDING_TABLES env var.
    - Search (query_text provided): runs VECTOR_SEARCH + ML.GENERATE_EMBEDDING
      against the specified table_path.

    Requires BIGQUERY_EMBEDDING_MODEL to be set for search mode.
    Distance metric is controlled by BIGQUERY_DISTANCE_TYPE (default: COSINE).
    """
    db = _get_db(ctx)

    if not inp.query_text.strip():
        await ctx.info("[bq_vector_search] discovery mode")
        return await db.discover_embedding_tables()

    await ctx.info(
        f"[bq_vector_search] search mode: table={inp.table_path!r} top_k={inp.top_k}"
    )
    cols = [c.strip() for c in inp.select_columns.split(",") if c.strip()] if inp.select_columns else None
    return await db.vector_search(
        query_text=inp.query_text.strip(),
        table_path=inp.table_path.strip(),
        embedding_column=inp.embedding_column.strip() or "embedding",
        top_k=inp.top_k,
        select_columns=cols,
    )
