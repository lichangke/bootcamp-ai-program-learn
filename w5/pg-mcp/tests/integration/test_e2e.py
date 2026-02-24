"""Integration tests using real PostgreSQL and mocked LLM generation."""

import os

import pytest
from pydantic import SecretStr

from pg_mcp.config.settings import (
    DatabaseConfig,
    QueryConfig,
    SchemaCacheConfig,
    SecurityConfig,
    Settings,
)
from pg_mcp.context import AppContext, clear_context, set_context
from pg_mcp.exceptions.errors import QueryExecutionError, QueryTimeoutError
from pg_mcp.security.validator import SQLValidator
from pg_mcp.server import query_database
from pg_mcp.services.executor import SQLExecutor
from pg_mcp.services.schema import SchemaService

pytestmark = pytest.mark.integration


def _integration_enabled() -> bool:
    return os.getenv("PG_MCP_RUN_INTEGRATION", "0") == "1"


@pytest.fixture(autouse=True)
def _cleanup_context() -> None:
    clear_context()
    yield
    clear_context()


@pytest.fixture
def integration_db_config() -> DatabaseConfig:
    return DatabaseConfig(
        name=os.getenv("PG_MCP_TEST_DB_NAME", "test_db"),
        host=os.getenv("PG_MCP_TEST_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("PG_MCP_TEST_DB_PORT", "5433")),
        database=os.getenv("PG_MCP_TEST_DB_DATABASE", "test_db"),
        username=os.getenv("PG_MCP_TEST_DB_USER", "test_user"),
        password=SecretStr(os.getenv("PG_MCP_TEST_DB_PASSWORD", "test_pass")),
        is_default=True,
    )


@pytest.fixture
def integration_query_config() -> QueryConfig:
    return QueryConfig(timeout_seconds=1, max_rows=10, max_rows_limit=100)


@pytest.fixture
async def integration_runtime(integration_db_config: DatabaseConfig, integration_query_config: QueryConfig):
    if not _integration_enabled():
        pytest.skip("Set PG_MCP_RUN_INTEGRATION=1 to run integration tests.")

    executor = SQLExecutor(integration_query_config)
    await executor.initialize([integration_db_config])
    schema_service = SchemaService(SchemaCacheConfig(ttl_minutes=60, auto_refresh=True))
    await schema_service.discover(integration_db_config.name, executor.get_pool(integration_db_config.name))
    validator = SQLValidator(SecurityConfig())

    class _MockLLM:
        def __init__(self):
            self.sql = "SELECT id, name FROM users ORDER BY id"

        async def generate_sql(self, natural_query: str, schema_info, dialect: str = "postgres") -> str:
            return self.sql

        async def close(self) -> None:
            return None

    llm = _MockLLM()
    settings = Settings(
        _env_file=None,
        deepseek={"api_key": "sk-test"},
        databases=[integration_db_config.model_dump(mode="json")],
        query=integration_query_config.model_dump(),
    )
    ctx = AppContext(
        settings=settings,
        validator=validator,
        executor=executor,
        schema_service=schema_service,
        llm_service=llm,  # type: ignore[arg-type]
    )
    set_context(ctx)

    try:
        yield {
            "executor": executor,
            "schema_service": schema_service,
            "llm": llm,
            "db_name": integration_db_config.name,
        }
    finally:
        await executor.close()


@pytest.mark.asyncio
async def test_schema_discovery_real_db(integration_runtime) -> None:
    schema = await integration_runtime["schema_service"].get_schema(integration_runtime["db_name"])
    assert schema is not None
    table_names = {(table.schema_name, table.name) for table in schema.tables}
    assert ("public", "users") in table_names
    assert ("public", "orders") in table_names


@pytest.mark.asyncio
async def test_read_only_write_rejected(integration_runtime) -> None:
    with pytest.raises(QueryExecutionError):
        await integration_runtime["executor"].execute(
            integration_runtime["db_name"],
            "INSERT INTO users(name, email, status) VALUES ('x', 'x@example.com', 'active')",
            limit=1,
        )


@pytest.mark.asyncio
async def test_limit_and_truncation(integration_runtime) -> None:
    result = await integration_runtime["executor"].execute(
        integration_runtime["db_name"],
        "SELECT id FROM users ORDER BY id",
        limit=2,
    )
    assert result.row_count == 2
    assert result.truncated is True


@pytest.mark.asyncio
async def test_timeout_handling(integration_runtime) -> None:
    with pytest.raises(QueryTimeoutError):
        await integration_runtime["executor"].execute(
            integration_runtime["db_name"],
            "SELECT pg_sleep(2)",
            limit=1,
        )


@pytest.mark.asyncio
async def test_full_flow_with_tool(integration_runtime) -> None:
    result = await query_database("list users", return_mode="both", limit=2)
    assert result["success"] is True
    assert result["data"]["sql"].upper().startswith("SELECT")
    assert result["data"]["result"]["row_count"] == 2
