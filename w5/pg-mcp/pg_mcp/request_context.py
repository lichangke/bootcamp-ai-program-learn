"""Request-scoped context helpers."""

from contextvars import ContextVar, Token

_request_id_ctx: ContextVar[str | None] = ContextVar("pg_mcp_request_id", default=None)


def set_request_id(request_id: str) -> Token:
    """Bind request_id for current async context and return reset token."""
    return _request_id_ctx.set(request_id)


def reset_request_id(token: Token) -> None:
    """Restore previous request_id context."""
    _request_id_ctx.reset(token)


def get_request_id() -> str | None:
    """Return current request_id from async context."""
    return _request_id_ctx.get()
