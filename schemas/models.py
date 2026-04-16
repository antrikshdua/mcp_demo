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


class MathOp(BaseModel):
    a: float = Field(description="First operand")
    b: float = Field(description="Second operand")


class WeatherQuery(BaseModel):
    city: str = Field(min_length=1, description="City name")
    units: str = Field(
        default="metric",
        pattern="^(metric|imperial)$",
        description="'metric' (°C) or 'imperial' (°F)",
    )
