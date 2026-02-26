"""Module entrypoint for `python -m pg_mcp`."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

from pg_mcp.config.settings import Settings
from pg_mcp.context import AppContext, clear_context, set_context
from pg_mcp.security.validator import SQLValidator
from pg_mcp.server import mcp
from pg_mcp.services.executor import SQLExecutor
from pg_mcp.services.llm import LLMService
from pg_mcp.services.rate_limiter import QueryRateLimiter
from pg_mcp.services.schema import SchemaService
from pg_mcp.utils.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(_server):
    """Initialize and clean up runtime dependencies."""
    executor: SQLExecutor | None = None
    llm_service: LLMService | None = None

    try:
        settings = Settings()
        configure_logging(settings.log_level)
        validator = SQLValidator(settings.security)

        executor = SQLExecutor(settings.query)
        await executor.initialize(settings.databases)

        healthy = executor.healthy_databases()
        unhealthy = executor.unhealthy_databases()
        if not healthy:
            raise RuntimeError("No healthy database connections available during startup.")

        schema_service = SchemaService(settings.schema_cache)
        if settings.schema_cache.preload_on_startup:
            # Preload is optional because full schema discovery across multiple
            # databases can exceed MCP client handshake time budgets.
            tasks = [
                schema_service.discover(db_config.name, executor.get_pool(db_config.name))
                for db_config in settings.databases
                if db_config.name in healthy
            ]
            await asyncio.gather(*tasks)

        llm_service = LLMService(settings.deepseek, schema_service)
        rate_limiter = QueryRateLimiter(
            max_concurrent_requests=settings.query.max_concurrent_requests,
            rate_limit_per_minute=settings.query.rate_limit_per_minute,
            window_seconds=settings.query.rate_limit_window_seconds,
        )
        set_context(
            AppContext(
                settings=settings,
                validator=validator,
                executor=executor,
                schema_service=schema_service,
                llm_service=llm_service,
                rate_limiter=rate_limiter,
            )
        )
        logger.info(
            "pg-mcp lifecycle initialized",
            extra={
                "event": "lifespan_initialized",
                "healthy_databases": healthy,
                "unhealthy_databases": unhealthy,
                "rate_limiter_enabled": rate_limiter.enabled,
            },
        )
        yield
    finally:
        clear_context()
        if llm_service is not None:
            await llm_service.close()
        if executor is not None:
            await executor.close()
        logger.info(
            "pg-mcp lifecycle closed",
            extra={
                "event": "lifespan_closed",
            },
        )


def _bind_lifespan() -> None:
    """Bind lifespan in a way compatible with FastMCP 2.x/3.x."""
    if hasattr(mcp, "_lifespan"):
        mcp._lifespan = app_lifespan
        return
    mcp.lifespan = app_lifespan


def _force_utf8_stdio() -> None:
    """Ensure stderr logs are UTF-8 so MCP clients can decode server logs."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _resolve_run_options(settings: Settings) -> tuple[str, dict[str, Any]]:
    """Build FastMCP run options from typed transport settings."""
    transport = settings.server.transport
    run_kwargs: dict[str, Any] = {
        "show_banner": settings.server.show_banner,
    }

    if transport in {"http", "sse", "streamable-http"}:
        run_kwargs.update(
            {
                "host": settings.server.host,
                "port": settings.server.port,
                "path": settings.server.path,
            }
        )
        if transport != "sse":
            run_kwargs["stateless_http"] = settings.server.stateless_http

    return transport, run_kwargs


def main() -> None:
    """Start FastMCP server."""
    settings = Settings()
    if settings.server.transport == "stdio":
        _force_utf8_stdio()
    configure_logging(settings.log_level)
    _bind_lifespan()
    transport, run_kwargs = _resolve_run_options(settings)
    mcp.run(transport=transport, **run_kwargs)


if __name__ == "__main__":
    main()

