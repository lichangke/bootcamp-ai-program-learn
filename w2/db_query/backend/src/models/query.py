from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from src.models import CamelCaseModel
from src.models.metadata import TableMetadata


class QueryRequest(CamelCaseModel):
    connection_name: str
    query_type: Literal["sql", "natural"] = "sql"
    content: str


class SqlQueryPayload(CamelCaseModel):
    sql: str = Field(min_length=1)


class NaturalQueryPayload(CamelCaseModel):
    prompt: str = Field(min_length=1)


class ColumnDefinition(CamelCaseModel):
    name: str
    type: str


class QueryResult(CamelCaseModel):
    columns: list[ColumnDefinition]
    rows: list[dict[str, object | None]]
    row_count: int
    execution_time: float
    query: str


class NaturalLanguageContext(CamelCaseModel):
    connection_name: str
    user_prompt: str
    relevant_tables: list[str]
    schema_context: dict[str, TableMetadata]
    generated_sql: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NaturalQueryResponse(CamelCaseModel):
    generated_sql: str
    context: NaturalLanguageContext
