from __future__ import annotations

import time
from typing import Any

from sqlglot import exp, parse

from src.models.query import ColumnDefinition, QueryResult


class QueryValidationError(ValueError):
    """Raised when SQL does not satisfy read-only constraints."""


class QueryService:
    def validate_sql(self, sql: str) -> str:
        if not sql.strip():
            raise QueryValidationError("SQL query cannot be empty")

        try:
            expressions = parse(sql, read="postgres")
        except Exception as exc:
            raise QueryValidationError(f"SQL syntax error: {exc}") from exc

        if len(expressions) != 1:
            raise QueryValidationError("Only a single SQL statement is allowed")

        expression = expressions[0]
        if not isinstance(expression, exp.Select):
            raise QueryValidationError("Only SELECT statements are allowed")

        return self.ensure_limit(sql, expression)

    def ensure_limit(self, raw_sql: str, expression: exp.Expression) -> str:
        if expression.args.get("limit") is not None:
            return raw_sql.strip().rstrip(";")
        sql_without_trailing_semicolon = raw_sql.strip().rstrip(";")
        return f"{sql_without_trailing_semicolon} LIMIT 1000"

    def execute_query(self, conn: Any, sql: str) -> QueryResult:
        start = time.perf_counter()
        with conn.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            description = cursor.description or []
        elapsed = time.perf_counter() - start

        columns = [
            ColumnDefinition(name=str(column.name), type=str(column.type_code))
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
