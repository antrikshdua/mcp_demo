"""
Pydantic models -- shared input/output schemas for the MCP server.
"""

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="Note title")
    body: str = Field(min_length=1, description="Note body text")
    tags: list[str] = Field(default_factory=list, description="Optional tags")


class NoteResult(BaseModel):
    id: str
    title: str
    body: str
    tags: list[str]
    created_at: str


class SearchQuery(BaseModel):
    query: str = Field(min_length=1, description="Search string")
    limit: int = Field(default=5, ge=1, le=50, description="Max results (1-50)")
    tags: list[str] = Field(default_factory=list, description="Filter by tags")


class WeatherQuery(BaseModel):
    city: str = Field(min_length=1, description="City name")
    units: str = Field(
        default="metric",
        pattern="^(metric|imperial)$",
        description="'metric' (°C) or 'imperial' (°F)",
    )


# ── BigQuery models ───────────────────────────────────────────────────────────

class BigQueryQueryInput(BaseModel):
    query: str = Field(
        min_length=1,
        description="BigQuery SQL SELECT (or WITH) query. Always include a LIMIT clause.",
    )


class DatasetListInput(BaseModel):
    search: str = Field(default="", description="Case-insensitive filter on dataset name")
    detailed: bool = Field(default=False, description="Include description and table count")
    max_results: int | None = Field(default=None, ge=1, description="Override default result cap")


class TableListInput(BaseModel):
    dataset_id: str = Field(min_length=1, description="BigQuery dataset ID")
    search: str = Field(default="", description="Case-insensitive filter on table name")
    detailed: bool = Field(default=False, description="Include row count, size, and type")
    max_results: int | None = Field(default=None, ge=1, description="Override default result cap")


class TableGetInput(BaseModel):
    dataset_id: str = Field(min_length=1, description="BigQuery dataset ID")
    table_id: str = Field(min_length=1, description="BigQuery table ID")


class VectorSearchInput(BaseModel):
    query_text: str = Field(
        default="",
        description="Text to search semantically. Leave empty for discovery mode (find embedding tables).",
    )
    table_path: str = Field(
        default="",
        description="Table path as 'dataset.table'. Required for search mode.",
    )
    top_k: int = Field(default=10, ge=1, le=1000, description="Number of results (1-1000)")
    select_columns: str = Field(
        default="",
        description="Comma-separated columns to return, or empty for all columns.",
    )
    embedding_column: str = Field(default="embedding", description="Name of the embedding column")
