"""Schema models used by SchemaService."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    """Column metadata."""

    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool = False
    comment: str | None = None


class TableInfo(BaseModel):
    """Table metadata."""

    name: str
    schema_name: str
    columns: list[ColumnInfo]
    comment: str | None = None


class SchemaInfo(BaseModel):
    """Database schema snapshot."""

    database: str
    tables: list[TableInfo]
    cached_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

