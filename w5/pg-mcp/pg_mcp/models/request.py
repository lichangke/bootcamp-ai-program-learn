"""Request models for MCP tools."""

from typing import Literal

from pydantic import BaseModel, Field

ReturnMode = Literal["sql", "result", "both"]


class QueryRequest(BaseModel):
    """Input payload for natural language database query."""

    query: str = Field(..., min_length=1, description="Natural language query description.")
    database: str | None = Field(None, description="Target database name.")
    return_mode: ReturnMode = Field("both", description="Response mode: sql, result, or both.")
    limit: int = Field(100, ge=1, le=1000, description="Result row limit.")

