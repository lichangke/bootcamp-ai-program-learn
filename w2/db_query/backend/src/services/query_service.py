from __future__ import annotations

import time
from typing import Any, cast

from sqlglot import exp, parse

from src.models.query import ColumnDefinition, QueryResult
from src.services.dialect_service import DatabaseDialect, sqlglot_dialect_name


class QueryValidationError(ValueError):
    """Raised when SQL does not satisfy read-only constraints."""


class QueryService:
    def validate_sql(
        self,
        sql: str,
        dialect: DatabaseDialect = DatabaseDialect.POSTGRES,
    ) -> str:
        if not sql.strip():
            raise QueryValidationError("SQL query cannot be empty")

        dialect_name = sqlglot_dialect_name(dialect)
        try:
            expressions = parse(sql, read=dialect_name)
        except Exception as exc:
            raise QueryValidationError(f"SQL syntax error: {exc}") from exc

        if len(expressions) != 1:
            raise QueryValidationError("Only a single SQL statement is allowed")

        expression = expressions[0]
        if not isinstance(expression, exp.Select):
            raise QueryValidationError("Only SELECT statements are allowed")

        return self.ensure_limit(expression, dialect)

    def ensure_limit(self, expression: exp.Expression, dialect: DatabaseDialect) -> str:
        dialect_name = sqlglot_dialect_name(dialect)
        if expression.args.get("limit") is not None:
            return expression.sql(dialect=dialect_name)
        select_expr = cast(exp.Select, expression.copy())
        limited = select_expr.limit(1000)
        return limited.sql(dialect=dialect_name)

    def _extract_column_name(self, column: Any) -> str:
        try:
            name = column.name
        except AttributeError:
            name = None
        if name is not None:
            return str(name)
        if isinstance(column, tuple) and column:
            return str(column[0])
        return "unknown"

    def _extract_column_type(self, column: Any) -> str:
        try:
            type_code = column.type_code
        except AttributeError:
            type_code = None
        if type_code is not None:
            return str(type_code)
        if isinstance(column, tuple) and len(column) > 1:
            return str(column[1])
        return "unknown"

    def execute_query(self, conn: Any, sql: str) -> QueryResult:
        start = time.perf_counter()
        with conn.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            description = cursor.description or []
        elapsed = time.perf_counter() - start

        columns = [
            ColumnDefinition(
                name=self._extract_column_name(column),
                type=self._extract_column_type(column),
            )
            for column in description
        ]

        result_rows: list[dict[str, object | None]] = []
        for row in rows:
            row_values: dict[str, object | None] = {}
            for index, column in enumerate(columns):
                row_values[column.name] = row[index] if index < len(row) else None
            result_rows.append(row_values)

        return QueryResult(
            columns=columns,
            rows=result_rows,
            row_count=len(result_rows),
            execution_time=elapsed,
            query=sql,
        )
