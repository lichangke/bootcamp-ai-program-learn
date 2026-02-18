from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, cast
from urllib.parse import ParseResult, parse_qs, unquote, urlparse

import pymysql

from src.models.metadata import ColumnMetadata, SchemaMetadata, TableMetadata


class MySqlAdapter:
    name: str = "mysql"
    schemes: tuple[str, ...] = ("mysql",)
    sqlglot_dialect: str = "mysql"

    def parse_url(self, url: str) -> ParseResult:
        return urlparse(url)

    def validate_url(self, url: str) -> ParseResult:
        parsed = self.parse_url(url)
        if parsed.scheme.lower() not in self.schemes:
            raise ValueError("Only MySQL URLs are supported by MySqlAdapter")
        if not parsed.hostname:
            raise ValueError("Database host is required")
        if not parsed.path or parsed.path == "/":
            raise ValueError("Database name is required in URL path")
        return parsed

    def _connect_kwargs(self, parsed: ParseResult, timeout: int) -> dict[str, Any]:
        params = parse_qs(parsed.query)
        return {
            "host": parsed.hostname,
            "user": unquote(parsed.username) if parsed.username else None,
            "password": unquote(parsed.password) if parsed.password else None,
            "database": parsed.path.lstrip("/"),
            "port": parsed.port or 3306,
            "connect_timeout": timeout,
            "charset": params.get("charset", ["utf8mb4"])[0],
            "autocommit": True,
        }

    def connect(self, url: str, timeout: int) -> Any:
        parsed = self.validate_url(url)
        kwargs = self._connect_kwargs(parsed, timeout=timeout)
        return pymysql.connect(**kwargs)

    def test_connection(self, url: str) -> None:
        with self.connect(url, timeout=5) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

    def fetch_metadata(self, connection_name: str, conn: Any) -> SchemaMetadata:
        database_name = self._get_database_name(conn)
        tables = self._get_tables_and_views(conn, database_name)
        table_columns = self._get_columns(conn, database_name)
        table_primary_keys = self._get_primary_keys(conn, database_name)

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

    def _get_database_name(self, conn: Any) -> str:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            row = cursor.fetchone()
        if not row or row[0] is None:
            return "unknown"
        return str(row[0])

    def _get_tables_and_views(self, conn: Any, database_name: str) -> list[tuple[str, str, str]]:
        query = """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = %s
            ORDER BY table_schema, table_name
        """
        with conn.cursor() as cursor:
            cursor.execute(query, (database_name,))
            rows = cursor.fetchall()

        results: list[tuple[str, str, str]] = []
        for schema_name, table_name, table_type in rows:
            normalized_type = "VIEW" if str(table_type).upper() == "VIEW" else "TABLE"
            results.append((str(schema_name), str(table_name), normalized_type))
        return results

    def _get_columns(
        self,
        conn: Any,
        database_name: str,
    ) -> dict[tuple[str, str], list[ColumnMetadata]]:
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
        with conn.cursor() as cursor:
            cursor.execute(query, (database_name,))
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
        database_name: str,
    ) -> dict[tuple[str, str], list[str]]:
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
        with conn.cursor() as cursor:
            cursor.execute(query, (database_name,))
            rows = cursor.fetchall()

        grouped: dict[tuple[str, str], list[str]] = {}
        for schema_name, table_name, column_name in rows:
            key = (str(schema_name), str(table_name))
            grouped.setdefault(key, []).append(str(column_name))
        return grouped

    def normalize_column_name(self, column: Any) -> str:
        name = getattr(column, "name", None)
        if name is not None:
            return str(name)
        if isinstance(column, tuple) and column:
            return str(column[0])
        return "unknown"

    def normalize_column_type(self, column: Any) -> str:
        type_code = getattr(column, "type_code", None)
        if type_code is not None:
            return str(type_code)
        if isinstance(column, tuple) and len(column) > 1:
            return str(column[1])
        return "unknown"

    def llm_dialect_label(self) -> str:
        return "MySQL"
