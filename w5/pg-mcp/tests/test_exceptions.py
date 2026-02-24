"""Tests for typed error hierarchy."""

from pg_mcp.exceptions.errors import (
    DatabaseConnectionError,
    DatabaseNotFoundError,
    ErrorCode,
    InvalidInputError,
    QueryExecutionError,
    QueryTimeoutError,
    SchemaNotReadyError,
    SecurityViolationError,
    SQLGenerationError,
)


def test_database_not_found_error() -> None:
    """DatabaseNotFoundError should expose code and details."""
    err = DatabaseNotFoundError("analytics")
    assert err.code == ErrorCode.DB_NOT_FOUND
    assert err.details == {"database": "analytics"}


def test_database_connection_error() -> None:
    """DatabaseConnectionError should contain reason details."""
    err = DatabaseConnectionError("analytics", "connection refused")
    assert err.code == ErrorCode.DB_CONNECTION_ERROR
    assert "connection refused" in err.message
    assert err.details["database"] == "analytics"


def test_schema_not_ready_error() -> None:
    """SchemaNotReadyError should use SCHEMA_NOT_READY code."""
    err = SchemaNotReadyError("analytics")
    assert err.code == ErrorCode.SCHEMA_NOT_READY
    assert err.details["database"] == "analytics"


def test_sql_generation_error() -> None:
    """SQLGenerationError should preserve original reason text."""
    err = SQLGenerationError("provider timeout")
    assert err.code == ErrorCode.SQL_GENERATION_ERROR
    assert "provider timeout" in err.message


def test_security_violation_error() -> None:
    """SecurityViolationError should include detected issue list."""
    err = SecurityViolationError("blocked", ["pg_sleep"])
    assert err.code == ErrorCode.SECURITY_VIOLATION
    assert err.details["detected_issues"] == ["pg_sleep"]


def test_query_timeout_error() -> None:
    """QueryTimeoutError should include timeout seconds in details."""
    err = QueryTimeoutError(30)
    assert err.code == ErrorCode.QUERY_TIMEOUT
    assert err.details["timeout_seconds"] == 30


def test_query_execution_error() -> None:
    """QueryExecutionError should use QUERY_EXECUTION_ERROR code."""
    err = QueryExecutionError("syntax error")
    assert err.code == ErrorCode.QUERY_EXECUTION_ERROR
    assert "syntax error" in err.message


def test_invalid_input_error() -> None:
    """InvalidInputError should support optional details payload."""
    err = InvalidInputError("bad return mode", {"field": "return_mode"})
    assert err.code == ErrorCode.INVALID_INPUT
    assert err.details["field"] == "return_mode"

