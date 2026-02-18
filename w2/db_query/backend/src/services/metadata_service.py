from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, cast

from src.models.metadata import ColumnMetadata, SchemaMetadata, TableMetadata
from src.services.dialect_service import DatabaseDialect


class MetadataService:
    def fetch_metadata(
        self,
        connection_name: str,
        conn: Any,
        dialect: DatabaseDialect,
    ) -> SchemaMetadata:
        database_name = self._get_database_name(conn, dialect)
        tables = self._get_tables_and_views(conn, dialect, database_name)
        table_columns = self._get_columns(conn, dialect, database_name)
        table_primary_keys = self._get_primary_keys(conn, dialect, database_name)

        table_models: list[TableMetadata] = []
        view_models: list[TableMetadata] = []

        for schema_name, table_name, table_type in tables:
            key = (schema_name, table_name)
            typed_table_type = cast(Literal["TABLE", "VIEW"], table_type)
            model = TableMetadata(
                schema_name=schema_name,
                table_name=table_name,
                table_type=typed_table_type,
                columns=table_columns.get(key, []),
                primary_keys=table_primary_keys.get(key, []),
            )
            if table_type == "VIEW":
                view_models.append(model)
            else:
                table_models.append(model)

        return SchemaMetadata(
            connection_name=connection_name,
            database_name=database_name,
            fetched_at=datetime.now(UTC),
            tables=table_models,
            views=view_models,
        )

    def _get_database_name(self, conn: Any, dialect: DatabaseDialect) -> str:
        query = (
            "SELECT current_database()"
            if dialect == DatabaseDialect.POSTGRES
            else "SELECT DATABASE()"
        )
        with conn.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()
        if not row or row[0] is None:
            return "unknown"
        return str(row[0])

    def _get_tables_and_views(
        self,
        conn: Any,
        dialect: DatabaseDialect,
        database_name: str,
    ) -> list[tuple[str, str, str]]:
        if dialect == DatabaseDialect.POSTGRES:
            query = """
                SELECT table_schema, table_name, table_type
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
            """
            params: tuple[str, ...] = ()
        else:
            query = """
                SELECT table_schema, table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY table_schema, table_name
            """
            params = (database_name,)

        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        results: list[tuple[str, str, str]] = []
        for row in rows:
            schema_name, table_name, table_type = row
            normalized_raw = str(table_type).upper()
            normalized_type = "VIEW" if normalized_raw == "VIEW" else "TABLE"
            results.append((str(schema_name), str(table_name), normalized_type))
        return results

    def _get_columns(
        self,
        conn: Any,
        dialect: DatabaseDialect,
        database_name: str,
    ) -> dict[tuple[str, str], list[ColumnMetadata]]:
        if dialect == DatabaseDialect.POSTGRES:
            query = """
                SELECT
                    table_schema,
                    table_name,
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length,
                    numeric_precision
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name, ordinal_position
            """
            params: tuple[str, ...] = ()
        else:
            query = """
                SELECT
                    table_schema,
                    table_name,
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length,
                    numeric_precision
                FROM information_schema.columns
                WHERE table_schema = %s
                ORDER BY table_schema, table_name, ordinal_position
            """
            params = (database_name,)

        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        grouped: dict[tuple[str, str], list[ColumnMetadata]] = {}
        for row in rows:
            (
                schema_name,
                table_name,
                column_name,
                data_type,
                is_nullable,
                default_value,
                max_length,
                precision,
            ) = row
            key = (str(schema_name), str(table_name))
            grouped.setdefault(key, []).append(
                ColumnMetadata(
                    column_name=str(column_name),
                    data_type=str(data_type),
                    is_nullable=str(is_nullable).upper() == "YES",
                    default_value=str(default_value) if default_value is not None else None,
                    max_length=int(max_length) if max_length is not None else None,
                    numeric_precision=int(precision) if precision is not None else None,
                )
            )
        return grouped

    def _get_primary_keys(
        self,
        conn: Any,
        dialect: DatabaseDialect,
        database_name: str,
    ) -> dict[tuple[str, str], list[str]]:
        if dialect == DatabaseDialect.POSTGRES:
            query = """
                SELECT
                    tc.table_schema,
                    tc.table_name,
                    kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                 AND tc.table_name = kcu.table_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position
            """
            params: tuple[str, ...] = ()
        else:
            query = """
                SELECT
                    tc.table_schema,
                    tc.table_name,
                    kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                 AND tc.table_name = kcu.table_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = %s
                ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position
            """
            params = (database_name,)

        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        grouped: dict[tuple[str, str], list[str]] = {}
        for row in rows:
            schema_name, table_name, column_name = row
            key = (str(schema_name), str(table_name))
            grouped.setdefault(key, []).append(str(column_name))
        return grouped
