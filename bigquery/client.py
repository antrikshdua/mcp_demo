"""Async BigQuery client wrapper — all blocking calls go through asyncio.to_thread()."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any

from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError

from .config import BigQueryConfig
from .query_safety import is_query_safe
from .auth import create_bigquery_client

logger = logging.getLogger("bigquery")

# Cache for embedding tables discovery (keyed by "embedding_tables")
_embedding_tables_cache: dict[str, list[dict[str, Any]]] = {}


def _setup_file_logger(log_file: str) -> None:
    """Attach a file handler to the bigquery logger."""
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] bigquery: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _create_job_config(
    cfg: BigQueryConfig,
    *,
    query_parameters: list[bigquery.ScalarQueryParameter] | None = None,
    dry_run: bool = False,
    use_query_cache: bool | None = None,
) -> bigquery.QueryJobConfig:
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=cfg.max_bytes_billed,
        dry_run=dry_run,
    )
    if query_parameters is not None:
        job_config.query_parameters = query_parameters
    if use_query_cache is not None:
        job_config.use_query_cache = use_query_cache
    return job_config


def _success(data: Any, **extra: Any) -> dict[str, Any]:
    return {"success": True, "data": data, **extra}


def _error(exc: Exception) -> dict[str, Any]:
    return {"success": False, "error": str(exc), "error_type": type(exc).__name__}


def _search_filter(items: list[Any], term: str, key_fn: Any) -> list[Any]:
    if not term:
        return items
    t = term.lower()
    return [i for i in items if t in key_fn(i).lower()]


def _fetch_limit(max_results: int, search: str) -> int:
    """Expand fetch window when filtering so we get enough candidates."""
    if not search:
        return max_results
    if max_results <= 10:
        multiplier = 20
    elif max_results <= 50:
        multiplier = 10
    else:
        multiplier = 5
    return min(max_results * multiplier, 1000)


def _table_type(table: Any, partition_info: dict | None = None) -> str:
    base = table.table_type
    partitioned = (
        (hasattr(table, "time_partitioning") and table.time_partitioning)
        or (hasattr(table, "range_partitioning") and table.range_partitioning)
        or partition_info is not None
    )
    return "PARTITIONED_TABLE" if partitioned and base == "TABLE" else base


def _partition_details(table_obj: Any) -> dict[str, Any] | None:
    if table_obj.time_partitioning:
        return {
            "type": table_obj.time_partitioning.type_,
            "field": table_obj.time_partitioning.field or "_PARTITIONTIME",
            "requires_filter": table_obj.time_partitioning.require_partition_filter,
        }
    if table_obj.range_partitioning:
        return {"type": "RANGE", "field": table_obj.range_partitioning.field}
    return None


def _primary_keys(table_obj: Any) -> list[str] | None:
    if (
        hasattr(table_obj, "table_constraints")
        and table_obj.table_constraints
        and table_obj.table_constraints.primary_key
    ):
        return list(table_obj.table_constraints.primary_key.columns)
    return None


class BigQueryDatabase:
    """All BigQuery tool operations in a single class.

    All I/O uses asyncio.to_thread() so the FastMCP event loop is never blocked.
    Instances are created once at server startup and injected via AppState.
    """

    def __init__(self, cfg: BigQueryConfig) -> None:
        self.cfg = cfg
        self.client = create_bigquery_client(
            project_id=cfg.project_id,
            location=cfg.location,
            key_file=cfg.key_file,
        )
        if cfg.log_file:
            _setup_file_logger(cfg.log_file)
        logger.info("BigQueryDatabase initialised (project=%s, location=%s)", cfg.project_id, cfg.location)

    # ── Query ─────────────────────────────────────────────────────────────────

    async def run_query(self, query: str) -> dict[str, Any]:
        """Execute a read-only SELECT / WITH query with full safety validation."""
        logger.info("run_query: %s", query[:120])
        is_safe, reason = is_query_safe(query)
        if not is_safe:
            return _error(ValueError(reason))

        try:
            job = self.client.query(query, job_config=_create_job_config(self.cfg))
            results = await asyncio.wait_for(
                asyncio.to_thread(job.result),
                timeout=self.cfg.timeout,
            )
            rows = [dict(row) for row in results]
            return _success(
                rows,
                total_count=len(rows),
                total_rows_in_result=results.total_rows,
                bytes_processed=job.total_bytes_processed,
                max_bytes_billed=self.cfg.max_bytes_billed,
            )
        except TimeoutError:
            return _error(TimeoutError(f"Query timed out after {self.cfg.timeout}s"))
        except (GoogleCloudError, Exception) as exc:
            logger.error("run_query error: %s", exc)
            return _error(exc)

    # ── Datasets ──────────────────────────────────────────────────────────────

    async def list_datasets(
        self,
        search: str = "",
        detailed: bool = False,
        max_results: int | None = None,
    ) -> dict[str, Any]:
        limit = max_results or (self.cfg.list_max_results_detailed if detailed else self.cfg.list_max_results)
        fetch = _fetch_limit(limit, search)

        try:
            datasets = await asyncio.to_thread(
                lambda: list(self.client.list_datasets(max_results=fetch))
            )
            total_available = len(datasets)

            if self.cfg.allowed_datasets:
                datasets = [d for d in datasets if d.dataset_id in self.cfg.allowed_datasets]

            if search:
                datasets = _search_filter(datasets, search, lambda d: d.dataset_id)

            total_matching = len(datasets)
            datasets = datasets[:limit]

            if detailed:
                rows = []
                for ds in datasets:
                    count = 0
                    try:
                        ref = self.client.dataset(ds.dataset_id)
                        tables = await asyncio.wait_for(
                            asyncio.to_thread(lambda r=ref: list(self.client.list_tables(r, max_results=1000))),
                            timeout=10.0,
                        )
                        count = len(tables)
                    except Exception:
                        pass
                    rows.append({
                        "dataset_id": ds.dataset_id,
                        "description": getattr(ds, "description", None),
                        "table_count": count,
                    })
                rows.sort(key=lambda x: x["dataset_id"])
                data: Any = rows
            else:
                data = sorted(d.dataset_id for d in datasets)

            return _success(
                data,
                total_available=total_available,
                total_matching=total_matching if search else total_available,
                returned_count=len(datasets),
            )
        except (GoogleCloudError, Exception) as exc:
            return _error(exc)

    # ── Tables ────────────────────────────────────────────────────────────────

    async def list_tables(
        self,
        dataset_id: str,
        search: str = "",
        detailed: bool = False,
        max_results: int | None = None,
    ) -> dict[str, Any]:
        if self.cfg.allowed_datasets and dataset_id not in self.cfg.allowed_datasets:
            return _error(PermissionError(f"Access to dataset '{dataset_id}' is not allowed"))

        limit = max_results or (self.cfg.list_max_results_detailed if detailed else self.cfg.list_max_results)
        fetch = _fetch_limit(limit, search)

        try:
            ref = self.client.dataset(dataset_id)
            ds_obj = await asyncio.to_thread(self.client.get_dataset, ref)
            tables = await asyncio.to_thread(
                lambda: list(self.client.list_tables(ref, max_results=fetch))
            )
            total_available = len(tables)

            if search:
                tables = _search_filter(tables, search, lambda t: t.table_id)
            total_matching = len(tables)
            tables = tables[:limit]

            dataset_context = {
                "dataset_id": dataset_id,
                "description": ds_obj.description,
                "location": ds_obj.location,
                "total_table_count": total_available,
            }

            if detailed:
                rows = []
                for t in tables:
                    t_ref = ref.table(t.table_id)
                    t_obj = await asyncio.to_thread(self.client.get_table, t_ref)
                    rows.append({
                        "table_id": t.table_id,
                        "type": _table_type(t),
                        "description": t_obj.description,
                        "row_count": t_obj.num_rows,
                        "size_bytes": t_obj.num_bytes,
                    })
                rows.sort(key=lambda x: x["table_id"])
                data2: Any = rows
            else:
                data2 = sorted(t.table_id for t in tables)

            return _success(
                data2,
                total_available=total_available,
                total_matching=total_matching if search else total_available,
                returned_count=len(tables),
                dataset_context=dataset_context,
            )
        except (GoogleCloudError, Exception) as exc:
            return _error(exc)

    # ── Table Detail ──────────────────────────────────────────────────────────

    async def get_table(self, dataset_id: str, table_id: str) -> dict[str, Any]:
        if self.cfg.allowed_datasets and dataset_id not in self.cfg.allowed_datasets:
            return _error(PermissionError(f"Access to dataset '{dataset_id}' is not allowed"))

        try:
            ref = self.client.dataset(dataset_id).table(table_id)
            t_obj = await asyncio.to_thread(self.client.get_table, ref)
            table_path = f"{dataset_id}.{table_id}"

            part = _partition_details(t_obj)
            pks = _primary_keys(t_obj)

            # Column fill rates
            fill_rates = await asyncio.to_thread(
                self._calculate_fill_rates, table_path, t_obj.schema
            )

            # Sample data — prefer ordering by the first timestamp column
            sample_data: list[dict] = []
            try:
                ts_cols = [f.name for f in t_obj.schema if f.field_type in ("TIMESTAMP", "DATETIME", "DATE")]
                order = f"ORDER BY `{ts_cols[0]}` DESC" if ts_cols else ""
                sq = f"SELECT * FROM `{table_path}` {order} LIMIT {self.cfg.sample_rows}"  # noqa: S608
                job = self.client.query(sq, job_config=_create_job_config(self.cfg))
                res = await asyncio.to_thread(job.result)
                sample_data = [dict(row) for row in res]
            except Exception:
                pass

            schema_stats = [
                {
                    "name": f.name,
                    "type": f.field_type,
                    "mode": f.mode,
                    "description": f.description,
                    "fill_rate_percent": fill_rates.get(f.name, 0.0),
                }
                for f in t_obj.schema
            ]

            return _success({
                "table_path": table_path,
                "type": _table_type(t_obj, part),
                "description": t_obj.description,
                "total_row_count": t_obj.num_rows,
                "size_bytes": t_obj.num_bytes,
                "created": t_obj.created.isoformat() if t_obj.created else None,
                "modified": t_obj.modified.isoformat() if t_obj.modified else None,
                "partition_details": part,
                "primary_key_columns": pks,
                "schema_with_fill_rates": schema_stats,
                "fill_rate_sample_size": self.cfg.sample_rows_for_stats if fill_rates else 0,
                "sample_data": sample_data,
            })
        except (GoogleCloudError, Exception) as exc:
            return _error(exc)

    def _calculate_fill_rates(
        self, table_path: str, schema: list[Any]
    ) -> dict[str, float]:
        """Blocking helper — call via asyncio.to_thread."""
        if not schema:
            return {}
        checks = [f"COUNTIF(`{f.name}` IS NOT NULL) AS `{f.name}_non_null`" for f in schema]
        query = (
            f"SELECT COUNT(*) AS total_rows, {', '.join(checks)} "  # noqa: S608
            f"FROM `{table_path}` LIMIT {self.cfg.sample_rows_for_stats}"
        )
        try:
            rows = list(self.client.query(query, job_config=_create_job_config(self.cfg)).result())
            if not rows:
                return {}
            row = rows[0]
            total = row["total_rows"]
            if total == 0:
                return {}
            return {f.name: round(row[f"{f.name}_non_null"] / total * 100, 1) for f in schema}
        except Exception:
            return {}

    # ── Vector Search ─────────────────────────────────────────────────────────

    async def discover_embedding_tables(self, refresh: bool = False) -> dict[str, Any]:
        cache_key = "embedding_tables"
        if not refresh and cache_key in _embedding_tables_cache:
            cached = _embedding_tables_cache[cache_key]
            return _success(cached, total_count=len(cached), cached=True, mode="discovery")

        # Use explicitly configured tables if available
        if self.cfg.embedding_tables:
            pattern = self.cfg.embedding_column_contains
            tables = [
                {
                    "dataset_id": p.split(".")[0],
                    "table_id": p.split(".")[1],
                    "full_path": p,
                    "embedding_column_contains": pattern,
                }
                for p in self.cfg.embedding_tables
                if len(p.split(".")) == 2
            ]
            _embedding_tables_cache[cache_key] = tables
            return _success(tables, total_count=len(tables), cached=False, mode="discovery",
                            source="BIGQUERY_EMBEDDING_TABLES")

        # Query INFORMATION_SCHEMA
        try:
            region = self.cfg.location or "US"
            pattern = self.cfg.embedding_column_contains
            q = (
                f"SELECT table_schema AS dataset_id, table_name AS table_id, column_name "  # noqa: S608
                f"FROM `{self.cfg.project_id}.region-{region}`.INFORMATION_SCHEMA.COLUMNS "
                f"WHERE data_type = 'ARRAY<FLOAT64>'"
            )
            if pattern:
                q += f" AND LOWER(column_name) LIKE '%{pattern.lower()}%'"
            if self.cfg.allowed_datasets:
                joined = "', '".join(self.cfg.allowed_datasets)
                q += f" AND table_schema IN ('{joined}')"
            q += " ORDER BY table_schema, table_name, column_name"

            job = self.client.query(q, job_config=_create_job_config(self.cfg))
            results = await asyncio.to_thread(job.result)

            tables_map: dict[str, dict] = {}
            for row in results:
                key = f"{row.dataset_id}.{row.table_id}"
                if key not in tables_map:
                    tables_map[key] = {
                        "dataset_id": row.dataset_id,
                        "table_id": row.table_id,
                        "full_path": key,
                        "embedding_columns": [],
                    }
                tables_map[key]["embedding_columns"].append(row.column_name)

            tables = list(tables_map.values())
            _embedding_tables_cache[cache_key] = tables
            return _success(tables, total_count=len(tables), cached=False, mode="discovery",
                            source="INFORMATION_SCHEMA")
        except GoogleCloudError as exc:
            if "Access Denied" in str(exc) or "403" in str(exc):
                return _error(PermissionError(
                    "Discovery requires 'BigQuery Metadata Viewer' role, "
                    "or set BIGQUERY_EMBEDDING_TABLES env var to skip auto-discovery."
                ))
            return _error(exc)

    async def vector_search(
        self,
        query_text: str,
        table_path: str,
        embedding_column: str = "embedding",
        top_k: int = 10,
        select_columns: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self.cfg.embedding_model:
            return _error(ValueError("BIGQUERY_EMBEDDING_MODEL is required for vector search."))

        distance_type = self.cfg.distance_type
        valid = ("COSINE", "EUCLIDEAN", "DOT_PRODUCT")
        if distance_type not in valid:
            return _error(ValueError(f"Invalid BIGQUERY_DISTANCE_TYPE '{distance_type}'. Must be one of {valid}"))

        if not 1 <= top_k <= 1000:
            return _error(ValueError("top_k must be between 1 and 1000"))

        select_clause = ", ".join(f"base.`{c}`" for c in select_columns) if select_columns else "base.*"
        model = self.cfg.embedding_model

        query = f"""
WITH query_embedding AS (
    SELECT ml_generate_embedding_result AS embedding
    FROM ML.GENERATE_EMBEDDING(
        MODEL `{model}`,
        (SELECT @query_text AS content),
        STRUCT(TRUE AS flatten_json_output)
    )
)
SELECT
    {select_clause},
    ROUND((1 - distance) * 100, 2) AS similarity_pct,
    distance
FROM VECTOR_SEARCH(
    TABLE `{table_path}`,
    '{embedding_column}',
    (SELECT embedding FROM query_embedding),
    top_k => {top_k},
    distance_type => '{distance_type}'
)
ORDER BY distance
"""  # noqa: S608

        try:
            job_config = _create_job_config(
                self.cfg,
                query_parameters=[bigquery.ScalarQueryParameter("query_text", "STRING", query_text)],
            )
            job = self.client.query(query, job_config=job_config)
            results = await asyncio.to_thread(job.result)
            rows = [dict(row) for row in results]

            return _success(
                rows,
                total_count=len(rows),
                mode="search",
                query_text=query_text,
                table_path=table_path,
                embedding_model=model,
                distance_type=distance_type,
                bytes_processed=job.total_bytes_processed,
                max_bytes_billed=self.cfg.max_bytes_billed,
                sql_query=query.replace("@query_text", f"'{query_text}'").strip(),
            )
        except (GoogleCloudError, Exception) as exc:
            return _error(exc)
