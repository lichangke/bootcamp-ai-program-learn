from __future__ import annotations

import time
from typing import Any, cast

from sqlglot import exp, parse

from src.domain.interfaces.db_adapter import DbAdapter
from src.models.query import ColumnDefinition, QueryResult


class QueryValidationError(ValueError):
    """Raised when SQL does not satisfy read-only constraints."""


class QueryService:
    def validate_sql(
        self,
        sql: str,
        sqlglot_dialect: str = "postgres",
    ) -> str:
        if not sql.strip():
            raise QueryValidationError("SQL query cannot be empty")

        try:
            expressions = parse(sql, read=sqlglot_dialect)
        except Exception as exc:
            raise QueryValidationError(f"SQL syntax error: {exc}") from exc

        if len(expressions) != 1:
            raise QueryValidationError("Only a single SQL statement is allowed")

        expression = expressions[0]
        if not isinstance(expression, exp.Select):
            raise QueryValidationError("Only SELECT statements are allowed")

        return self.ensure_limit(expression, sqlglot_dialect)

    def ensure_limit(self, expression: exp.Expression, sqlglot_dialect: str) -> str:
        if expression.args.get("limit") is not None:
            return expression.sql(dialect=sqlglot_dialect)
        select_expr = cast(exp.Select, expression.copy())
        limited = select_expr.limit(1000)
        return limited.sql(dialect=sqlglot_dialect)

    def execute_query(self, conn: Any, sql: str, adapter: DbAdapter) -> QueryResult:
        start = time.perf_counter()
        with conn.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            description = cursor.description or []
        elapsed = time.perf_counter() - start

        columns = [
            ColumnDefinition(
                name=adapter.normalize_column_name(column),
                type=adapter.normalize_column_type(column),
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
