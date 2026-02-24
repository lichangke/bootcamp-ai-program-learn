"""Typed domain errors used by pg-mcp."""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Error codes exposed to clients."""

    DB_NOT_FOUND = "DB_NOT_FOUND"
    DB_CONNECTION_ERROR = "DB_CONNECTION_ERROR"
    SCHEMA_NOT_READY = "SCHEMA_NOT_READY"
    SQL_GENERATION_ERROR = "SQL_GENERATION_ERROR"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    QUERY_EXECUTION_ERROR = "QUERY_EXECUTION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


class PgMcpError(Exception):
    """Base exception with machine-readable metadata."""

    def __init__(self, code: ErrorCode, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class DatabaseNotFoundError(PgMcpError):
    """Raised when requested database name is absent in config."""

    def __init__(self, db_name: str):
        super().__init__(
            ErrorCode.DB_NOT_FOUND,
            f"Database '{db_name}' is not configured.",
            {"database": db_name},
        )


class DatabaseConnectionError(PgMcpError):
    """Raised when a database pool cannot be created."""

    def __init__(self, db_name: str, reason: str):
        super().__init__(
            ErrorCode.DB_CONNECTION_ERROR,
            f"Failed to connect to database '{db_name}': {reason}",
            {"database": db_name, "reason": reason},
        )


class SchemaNotReadyError(PgMcpError):
    """Raised when schema cache is unavailable for a database."""

    def __init__(self, db_name: str):
        super().__init__(
            ErrorCode.SCHEMA_NOT_READY,
            f"Schema cache is not ready for database '{db_name}'.",
            {"database": db_name},
        )


class SQLGenerationError(PgMcpError):
    """Raised when LLM generation fails."""

    def __init__(self, message: str):
        super().__init__(
            ErrorCode.SQL_GENERATION_ERROR,
            f"SQL generation failed: {message}",
        )


class SecurityViolationError(PgMcpError):
    """Raised when SQL violates read-only policy."""

    def __init__(self, message: str, detected_issues: list[str]):
        super().__init__(
            ErrorCode.SECURITY_VIOLATION,
            message,
            {"detected_issues": detected_issues},
        )


class QueryTimeoutError(PgMcpError):
    """Raised when statement timeout is reached."""

    def __init__(self, timeout_seconds: int):
        super().__init__(
            ErrorCode.QUERY_TIMEOUT,
            f"Query execution exceeded timeout ({timeout_seconds}s).",
            {"timeout_seconds": timeout_seconds},
        )


class QueryExecutionError(PgMcpError):
    """Raised for non-timeout database execution errors."""

    def __init__(self, message: str):
        super().__init__(
            ErrorCode.QUERY_EXECUTION_ERROR,
            f"Query execution failed: {message}",
        )


class InvalidInputError(PgMcpError):
    """Raised for invalid request parameters."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            ErrorCode.INVALID_INPUT,
            message,
            details,
        )
