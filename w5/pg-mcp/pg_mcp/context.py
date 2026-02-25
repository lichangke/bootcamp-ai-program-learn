"""Application context container and access helpers."""

from contextvars import Token
from dataclasses import dataclass

from pg_mcp.config.settings import Settings
from pg_mcp.request_context import (
    get_request_id as _get_request_id,
)
from pg_mcp.request_context import (
    reset_request_id as _reset_request_id,
)
from pg_mcp.request_context import (
    set_request_id as _set_request_id,
)
from pg_mcp.security.validator import SQLValidator
from pg_mcp.services.executor import SQLExecutor
from pg_mcp.services.llm import LLMService
from pg_mcp.services.rate_limiter import QueryRateLimiter
from pg_mcp.services.schema import SchemaService


@dataclass
class AppContext:
    """Dependency container for runtime services."""

    settings: Settings
    validator: SQLValidator
    executor: SQLExecutor
    schema_service: SchemaService
    llm_service: LLMService
    rate_limiter: QueryRateLimiter | None = None

    async def close(self) -> None:
        """Close managed resources."""
        await self.llm_service.close()
        await self.executor.close()


_context: AppContext | None = None


def get_context() -> AppContext:
    """Return globally registered app context."""
    if _context is None:
        raise RuntimeError("AppContext is not initialized.")
    return _context


def set_context(ctx: AppContext) -> None:
    """Set global app context reference."""
    global _context
    _context = ctx


def clear_context() -> None:
    """Clear global app context reference."""
    global _context
    _context = None


def set_request_id(request_id: str) -> Token:
    """Bind request_id for current async context and return reset token."""
    return _set_request_id(request_id)


def reset_request_id(token: Token) -> None:
    """Restore previous request_id context."""
    _reset_request_id(token)


def get_request_id() -> str | None:
    """Return current request_id from async context."""
    return _get_request_id()
