"""Module entrypoint for `python -m pg_mcp`."""

from contextlib import asynccontextmanager

from pg_mcp.config.settings import Settings
from pg_mcp.context import AppContext, clear_context, set_context
from pg_mcp.security.validator import SQLValidator
from pg_mcp.server import mcp
from pg_mcp.services.executor import SQLExecutor
from pg_mcp.services.llm import LLMService
from pg_mcp.services.schema import SchemaService


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
        for db_config in settings.databases:
            await schema_service.discover(db_config.name, executor.get_pool(db_config.name))

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
        print("pg-mcp lifecycle initialized")
        yield
    finally:
        clear_context()
        if llm_service is not None:
            await llm_service.close()
        if executor is not None:
            await executor.close()
        print("pg-mcp lifecycle closed")


def main() -> None:
    """Start FastMCP server."""
    mcp.lifespan = app_lifespan
    mcp.run()


if __name__ == "__main__":
    main()

