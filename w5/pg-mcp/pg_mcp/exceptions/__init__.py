"""Domain exceptions."""

from pg_mcp.exceptions.errors import (
    DatabaseConnectionError,
    DatabaseNotFoundError,
    ErrorCode,
    InvalidInputError,
    PgMcpError,
    QueryExecutionError,
    QueryTimeoutError,
    RateLimitExceededError,
    SchemaNotReadyError,
    SecurityViolationError,
    SQLGenerationError,
)

__all__ = [
    "DatabaseConnectionError",
    "DatabaseNotFoundError",
    "ErrorCode",
    "InvalidInputError",
    "PgMcpError",
    "QueryExecutionError",
    "RateLimitExceededError",
    "QueryTimeoutError",
    "SQLGenerationError",
    "SchemaNotReadyError",
    "SecurityViolationError",
]
