"""SQL safety validator based on SQLGlot AST."""

import logging
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp

from pg_mcp.config.settings import SecurityConfig
from pg_mcp.request_context import get_request_id

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Outcome of SQL safety validation."""

    is_safe: bool
    message: str = ""
    detected_issues: list[str] = field(default_factory=list)


class SQLValidator:
    """Read-only SQL validator using allow-list + deny-list checks."""

    _EXPLICITLY_BLOCKED_STATEMENTS = {
        "Insert",
        "Update",
        "Delete",
        "Drop",
        "TruncateTable",
        "Create",
        "Alter",
        "Merge",
        "Command",
        "Use",
        "Set",
    }

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.allowed_nodes = set(config.allowed_ast_nodes)
        self.allowed_top_level = set(config.allowed_statement_types) | {
            "With",
            "Union",
            "Intersect",
            "Except",
            "Select",
        }
        self.blocked_functions = {fn.lower() for fn in config.blocked_functions}
        self.blocked_constructs = set(config.blocked_constructs)

    def validate(self, sql: str) -> ValidationResult:
        """Validate SQL and reject anything that is not read-only."""
        if not sql or not sql.strip():
            return ValidationResult(is_safe=False, message="SQL statement is empty.")

        try:
            statements = sqlglot.parse(sql, dialect="postgres")
        except Exception as exc:
            return ValidationResult(is_safe=False, message=f"SQL parse failed: {exc}")

        if not statements:
            return ValidationResult(is_safe=False, message="SQL statement is empty.")

        issues: list[str] = []
        for stmt in statements:
            issues.extend(self._check_top_level_statement(stmt))
            issues.extend(self._check_ast_nodes_whitelist(stmt))
            issues.extend(self._check_blocked_functions(stmt))
            issues.extend(self._check_blocked_constructs(stmt))

        unique_issues = sorted(set(issues))
        if unique_issues:
            logger.warning(
                "sql_validation_failed",
                extra={
                    "event": "sql_validation_failed",
                    "request_id": get_request_id(),
                    "issue_count": len(unique_issues),
                },
            )
            return ValidationResult(
                is_safe=False,
                message="Detected non-read-only operation; only SELECT-like queries are allowed.",
                detected_issues=unique_issues,
            )
        logger.info(
            "sql_validation_passed",
            extra={
                "event": "sql_validation_passed",
                "request_id": get_request_id(),
            },
        )
        return ValidationResult(is_safe=True, message="Validation passed.")

    def _check_top_level_statement(self, stmt: exp.Expression) -> list[str]:
        """Ensure top-level statement is read-only."""
        issues: list[str] = []
        stmt_type = stmt.__class__.__name__

        if stmt_type not in self.allowed_top_level:
            issues.append(f"Top-level statement '{stmt_type}' is not allowed.")

        if isinstance(stmt, exp.With):
            with_body = stmt.this
            if with_body is not None and with_body.__class__.__name__ not in self.allowed_top_level:
                issues.append(f"WITH body statement '{with_body.__class__.__name__}' is not allowed.")

        return issues

    def _check_ast_nodes_whitelist(self, stmt: exp.Expression) -> list[str]:
        """Block unknown AST node types by default."""
        issues: list[str] = []
        for node in stmt.walk():
            node_type = node.__class__.__name__
            if node_type in self._EXPLICITLY_BLOCKED_STATEMENTS:
                issues.append(f"Dangerous statement node '{node_type}' detected.")
                continue
            if node_type not in self.allowed_nodes:
                issues.append(f"AST node '{node_type}' is not in allowed list.")
        return issues

    def _check_blocked_functions(self, stmt: exp.Expression) -> list[str]:
        """Block explicitly dangerous PostgreSQL functions."""
        issues: list[str] = []
        for node in stmt.walk():
            if not isinstance(node, exp.Func):
                continue

            func_name = self._extract_function_name(node)
            if not func_name:
                continue
            if func_name.lower() in self.blocked_functions:
                issues.append(f"Blocked function call detected: {func_name}.")
        return issues

    def _check_blocked_constructs(self, stmt: exp.Expression) -> list[str]:
        """Block high-risk constructs like SELECT INTO and COPY."""
        issues: list[str] = []

        if stmt.args.get("into") is not None:
            issues.append("SELECT INTO is not allowed.")

        for node in stmt.walk():
            node_type = node.__class__.__name__
            if node_type in self.blocked_constructs:
                issues.append(f"Blocked SQL construct detected: {node_type}.")
            if isinstance(node, exp.Copy):
                issues.append("COPY statement is not allowed.")
        return issues

    def get_query_info(self, sql: str) -> dict[str, Any]:
        """Extract metadata for auditing and diagnostics."""
        statements = sqlglot.parse(sql, dialect="postgres")
        statement_types = [stmt.__class__.__name__ for stmt in statements]

        tables: set[str] = set()
        columns: set[str] = set()
        functions: set[str] = set()
        has_limit = False
        has_order_by = False

        for stmt in statements:
            if stmt.args.get("limit") is not None:
                has_limit = True
            if stmt.args.get("order") is not None:
                has_order_by = True

            for table in stmt.find_all(exp.Table):
                if table.db:
                    tables.add(f"{table.db}.{table.name}")
                else:
                    tables.add(table.name)

            for column in stmt.find_all(exp.Column):
                columns.add(column.sql(dialect="postgres"))

            for func in stmt.find_all(exp.Func):
                func_name = self._extract_function_name(func)
                if func_name:
                    functions.add(func_name.lower())

        return {
            "statement_types": statement_types,
            "tables": sorted(tables),
            "columns": sorted(columns),
            "functions": sorted(functions),
            "has_limit": has_limit,
            "has_order_by": has_order_by,
        }

    @staticmethod
    def _extract_function_name(node: exp.Func) -> str:
        """Return normalized function name for both built-ins and anonymous functions."""
        if isinstance(node, exp.Anonymous):
            return node.name or ""

        sql_name = node.sql_name()
        if sql_name:
            return sql_name

        return node.__class__.__name__
