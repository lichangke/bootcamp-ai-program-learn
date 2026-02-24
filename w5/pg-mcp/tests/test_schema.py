"""Tests for schema models and schema service caching behavior."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from pg_mcp.models.schema import ColumnInfo, SchemaInfo, TableInfo
from pg_mcp.services.schema import SchemaService


def _make_pool_with_rows(rows: list[dict]) -> Mock:
    conn = AsyncMock()
    conn.fetch.return_value = rows
    pool = Mock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    acquire_ctx.__aexit__.return_value = False
    pool.acquire.return_value = acquire_ctx
    return pool


def test_schema_models_construct() -> None:
    """Schema models should construct and serialize correctly."""
    column = ColumnInfo(name="id", data_type="integer", nullable=False, is_primary_key=True, comment="pk")
    table = TableInfo(name="users", schema_name="public", columns=[column], comment="app users")
    schema = SchemaInfo(database="analytics", tables=[table], cached_at=datetime.now(UTC))

    payload = schema.model_dump()
    assert payload["database"] == "analytics"
    assert payload["tables"][0]["columns"][0]["is_primary_key"] is True


@pytest.mark.asyncio
async def test_discover_builds_schema_cache(schema_cache_config) -> None:
    """discover should aggregate rows into table/column models and cache the result."""
    service = SchemaService(schema_cache_config)
    rows = [
        {
            "table_schema": "public",
            "table_name": "users",
            "table_comment": "users table",
            "column_name": "id",
            "data_type": "integer",
            "is_nullable": "NO",
            "ordinal_position": 1,
            "column_comment": "primary key",
            "is_primary_key": True,
        },
        {
            "table_schema": "public",
            "table_name": "users",
            "table_comment": "users table",
            "column_name": "email",
            "data_type": "text",
            "is_nullable": "NO",
            "ordinal_position": 2,
            "column_comment": "login email",
            "is_primary_key": False,
        },
        {
            "table_schema": "sales",
            "table_name": "orders",
            "table_comment": None,
            "column_name": "id",
            "data_type": "integer",
            "is_nullable": "NO",
            "ordinal_position": 1,
            "column_comment": None,
            "is_primary_key": True,
        },
    ]
    pool = _make_pool_with_rows(rows)

    schema = await service.discover("analytics", pool)
    assert len(schema.tables) == 2
    assert schema.cached_at.tzinfo is not None
    assert schema.tables[0].columns[0].name == "id"


@pytest.mark.asyncio
async def test_get_schema_returns_none_when_missing(schema_cache_config) -> None:
    """Cache miss should return None."""
    service = SchemaService(schema_cache_config)
    assert await service.get_schema("missing") is None


@pytest.mark.asyncio
async def test_get_schema_hits_cache_when_not_expired(schema_cache_config) -> None:
    """Fresh cache should return stored schema directly."""
    service = SchemaService(schema_cache_config)
    schema = SchemaInfo(database="analytics", tables=[], cached_at=datetime.now(UTC))
    service._cache["analytics"] = schema

    cached = await service.get_schema("analytics")
    assert cached is schema


@pytest.mark.asyncio
async def test_get_schema_auto_refresh_on_expiry(schema_cache_config) -> None:
    """Expired cache should auto-refresh when pool is supplied and auto_refresh is enabled."""
    service = SchemaService(schema_cache_config)
    stale = SchemaInfo(
        database="analytics",
        tables=[],
        cached_at=datetime.now(UTC) - timedelta(minutes=999),
    )
    fresh = SchemaInfo(database="analytics", tables=[], cached_at=datetime.now(UTC))
    service._cache["analytics"] = stale
    service.discover = AsyncMock(return_value=fresh)  # type: ignore[method-assign]

    result = await service.get_schema("analytics", pool=AsyncMock())
    assert result is fresh
    service.discover.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_schema_returns_stale_cache_when_refresh_fails(schema_cache_config) -> None:
    """Expired cache should degrade gracefully if refresh fails."""
    service = SchemaService(schema_cache_config)
    stale = SchemaInfo(
        database="analytics",
        tables=[],
        cached_at=datetime.now(UTC) - timedelta(minutes=999),
    )
    service._cache["analytics"] = stale
    service.discover = AsyncMock(side_effect=RuntimeError("db unavailable"))  # type: ignore[method-assign]

    result = await service.get_schema("analytics", pool=AsyncMock())
    assert result is stale


def test_format_for_llm(schema_cache_config) -> None:
    """LLM formatter should include table names, columns, PK and nullability markers."""
    service = SchemaService(schema_cache_config)
    schema = SchemaInfo(
        database="analytics",
        tables=[
            TableInfo(
                name="users",
                schema_name="public",
                comment="users table",
                columns=[
                    ColumnInfo(name="id", data_type="integer", nullable=False, is_primary_key=True, comment="pk"),
                    ColumnInfo(name="email", data_type="text", nullable=False, is_primary_key=False, comment=None),
                ],
            )
        ],
        cached_at=datetime.now(UTC),
    )

    text = service.format_for_llm(schema)
    assert "Table: public.users -- users table" in text
    assert "id: integer [PK] NOT NULL -- pk" in text
    assert "email: text NOT NULL" in text


def test_invalidate_cache(schema_cache_config) -> None:
    """invalidate_cache should support single-db and full invalidation."""
    service = SchemaService(schema_cache_config)
    service._cache["db1"] = SchemaInfo(database="db1", tables=[], cached_at=datetime.now(UTC))
    service._cache["db2"] = SchemaInfo(database="db2", tables=[], cached_at=datetime.now(UTC))

    service.invalidate_cache("db1")
    assert "db1" not in service._cache
    assert "db2" in service._cache

    service.invalidate_cache()
    assert service._cache == {}
