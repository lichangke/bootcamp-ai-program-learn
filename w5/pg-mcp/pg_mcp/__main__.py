"""Module entrypoint for `python -m pg_mcp`."""

import asyncio
from contextlib import asynccontextmanager
import logging
import sys

from pg_mcp.config.settings import Settings
from pg_mcp.context import AppContext, clear_context, set_context
from pg_mcp.security.validator import SQLValidator
from pg_mcp.server import mcp
from pg_mcp.services.executor import SQLExecutor
from pg_mcp.services.llm import LLMService
from pg_mcp.services.schema import SchemaService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(_server):
    """Initialize and clean up runtime dependencies."""
    executor: SQLExecutor | None = None
    llm_service: LLMService | None = None

    try:
        settings = Settings()
        validator = SQLValidator(settings.security)

        executor = SQLExecutor(settings.query)
        await executor.initialize(settings.databases)

        schema_service = SchemaService(settings.schema_cache)
        if settings.schema_cache.preload_on_startup:
            # Preload is optional because full schema discovery across multiple
            # databases can exceed MCP client handshake time budgets.
            tasks = [
                schema_service.discover(db_config.name, executor.get_pool(db_config.name))
                for db_config in settings.databases
            ]
            await asyncio.gather(*tasks)

        llm_service = LLMService(settings.deepseek, schema_service)
        set_context(
            AppContext(
                settings=settings,
                validator=validator,
                executor=executor,
                schema_service=schema_service,
                llm_service=llm_service,
            )
        )
        logger.info("pg-mcp lifecycle initialized")
        yield
    finally:
        clear_context()
        if llm_service is not None:
            await llm_service.close()
        if executor is not None:
            await executor.close()
        logger.info("pg-mcp lifecycle closed")


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


def main() -> None:
    """Start FastMCP server."""
    _force_utf8_stdio()
    _bind_lifespan()
    mcp.run(show_banner=False)


if __name__ == "__main__":
    main()

