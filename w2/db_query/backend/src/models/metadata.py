from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from src.models import CamelCaseModel


class ColumnMetadata(CamelCaseModel):
    column_name: str
    data_type: str
    is_nullable: bool
    default_value: str | None = None
    max_length: int | None = None
    numeric_precision: int | None = None


class TableMetadata(CamelCaseModel):
    schema_name: str
    table_name: str
    table_type: Literal["TABLE", "VIEW"]
    columns: list[ColumnMetadata]
    primary_keys: list[str] = Field(default_factory=list)


class SchemaMetadata(CamelCaseModel):
    connection_name: str
    database_name: str
    fetched_at: datetime
    tables: list[TableMetadata]
    views: list[TableMetadata]

