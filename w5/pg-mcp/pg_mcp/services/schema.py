"""Schema discovery + cache service."""

import logging
from datetime import UTC, datetime, timedelta

import asyncpg

from pg_mcp.config.settings import SchemaCacheConfig
from pg_mcp.models.schema import ColumnInfo, SchemaInfo, TableInfo
from pg_mcp.request_context import get_request_id

SCHEMA_DISCOVERY_SQL = """
WITH user_tables AS (
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_type = 'BASE TABLE'
      AND table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
),
table_comments AS (
    SELECT
        n.nspname AS table_schema,
        c.relname AS table_name,
        pg_catalog.obj_description(c.oid, 'pg_class') AS table_comment
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r'
      AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
),
primary_keys AS (
    SELECT
        kcu.table_schema,
        kcu.table_name,
        kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
     AND tc.table_schema = kcu.table_schema
     AND tc.table_name = kcu.table_name
    WHERE tc.constraint_type = 'PRIMARY KEY'
),
table_columns AS (
    SELECT
        c.table_schema,
        c.table_name,
        c.column_name,
        c.data_type,
        c.is_nullable,
        c.ordinal_position,
        pg_catalog.col_description(
            to_regclass(format('%I.%I', c.table_schema, c.table_name)),
            c.ordinal_position
        ) AS column_comment
    FROM information_schema.columns c
    JOIN user_tables t
      ON t.table_schema = c.table_schema
     AND t.table_name = c.table_name
)
SELECT
    c.table_schema,
    c.table_name,
    tc.table_comment,
    c.column_name,
    c.data_type,
    c.is_nullable,
    c.ordinal_position,
    c.column_comment,
    (pk.column_name IS NOT NULL) AS is_primary_key
FROM table_columns c
LEFT JOIN table_comments tc
  ON tc.table_schema = c.table_schema
 AND tc.table_name = c.table_name
LEFT JOIN primary_keys pk
  ON pk.table_schema = c.table_schema
 AND pk.table_name = c.table_name
 AND pk.column_name = c.column_name
ORDER BY c.table_schema, c.table_name, c.ordinal_position;
"""

logger = logging.getLogger(__name__)


class SchemaService:
    """Manage schema discovery and in-memory TTL cache."""

    def __init__(self, cache_config: SchemaCacheConfig):
        self.cache_config = cache_config
        self._cache: dict[str, SchemaInfo] = {}

    async def discover(self, db_name: str, pool: asyncpg.Pool) -> SchemaInfo:
        """Fetch full database schema in one SQL round trip."""
        logger.info(
            "schema_discover_start",
            extra={
                "event": "schema_discover_start",
                "request_id": get_request_id(),
                "database": db_name,
            },
        )
        async with pool.acquire() as conn:
            rows = await conn.fetch(SCHEMA_DISCOVERY_SQL)

        grouped_tables: dict[tuple[str, str], dict] = {}
        for row in rows:
            schema_name = row["table_schema"]
            table_name = row["table_name"]
            table_key = (schema_name, table_name)
            table = grouped_tables.setdefault(
                table_key,
                {
                    "comment": row.get("table_comment"),
                    "columns": [],
                },
            )
            table["columns"].append(
                (
                    int(row["ordinal_position"]),
                    ColumnInfo(
                        name=row["column_name"],
                        data_type=row["data_type"],
                        nullable=row["is_nullable"] == "YES",
                        is_primary_key=bool(row["is_primary_key"]),
                        comment=row.get("column_comment"),
                    ),
                )
            )

        tables: list[TableInfo] = []
        for (schema_name, table_name), payload in sorted(grouped_tables.items()):
            columns = [column for _, column in sorted(payload["columns"], key=lambda item: item[0])]
            tables.append(
                TableInfo(
                    name=table_name,
                    schema_name=schema_name,
                    columns=columns,
                    comment=payload["comment"],
                )
            )

        schema_info = SchemaInfo(
            database=db_name,
            tables=tables,
            cached_at=datetime.now(UTC),
        )
        self._cache[db_name] = schema_info
        logger.info(
            "schema_discover_success",
            extra={
                "event": "schema_discover_success",
                "request_id": get_request_id(),
                "database": db_name,
                "table_count": len(tables),
            },
        )
        return schema_info

    async def get_schema(self, db_name: str, pool: asyncpg.Pool | None = None) -> SchemaInfo | None:
        """Return cached schema, optionally auto-refreshing stale cache."""
        cached = self._cache.get(db_name)
        if cached is None:
            if self.cache_config.auto_refresh and pool is not None:
                try:
                    return await self.discover(db_name, pool)
                except Exception:
                    logger.warning(
                        "schema_discover_failed",
                        extra={
                            "event": "schema_discover_failed",
                            "request_id": get_request_id(),
                            "database": db_name,
                        },
                    )
                    return None
            return None

        if not self.is_cache_expired(db_name):
            return cached

        if self.cache_config.auto_refresh and pool is not None:
            try:
                return await self.discover(db_name, pool)
            except Exception:
                logger.warning(
                    "schema_refresh_failed",
                    extra={
                        "event": "schema_refresh_failed",
                        "request_id": get_request_id(),
                        "database": db_name,
                    },
                )
                return cached

        return cached

    def is_cache_expired(self, db_name: str) -> bool:
        """Return whether the selected schema cache entry is stale."""
        schema_info = self._cache.get(db_name)
        if schema_info is None:
            return True

        cached_at = schema_info.cached_at
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=UTC)

        expires_at = cached_at + timedelta(minutes=self.cache_config.ttl_minutes)
        return datetime.now(UTC) >= expires_at

    def invalidate_cache(self, db_name: str | None = None) -> None:
        """Invalidate one database cache entry or the full cache."""
        if db_name is None:
            self._cache.clear()
            return
        self._cache.pop(db_name, None)

    def format_for_llm(self, schema_info: SchemaInfo) -> str:
        """Build compact schema text prompt for SQL generation."""
        if not schema_info.tables:
            return "No tables discovered."

        lines: list[str] = []
        for table in sorted(schema_info.tables, key=lambda t: (t.schema_name, t.name)):
            table_comment = f" -- {table.comment}" if table.comment else ""
            lines.append(f"Table: {table.schema_name}.{table.name}{table_comment}")
            for column in table.columns:
                pk = " [PK]" if column.is_primary_key else ""
                not_null = " NOT NULL" if not column.nullable else ""
                col_comment = f" -- {column.comment}" if column.comment else ""
                lines.append(f"  - {column.name}: {column.data_type}{pk}{not_null}{col_comment}")
        return "\n".join(lines)
