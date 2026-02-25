"""Tests for SQLExecutor."""

from unittest.mock import AsyncMock, Mock

import asyncpg
import pytest

from pg_mcp.exceptions.errors import DatabaseConnectionError, DatabaseNotFoundError, QueryTimeoutError
from pg_mcp.services.executor import QueryResult, SQLExecutor


def _make_pool_and_connection(records: list[dict] | None = None) -> tuple[Mock, AsyncMock]:
    conn = AsyncMock()
    conn.fetch.return_value = records or []
    pool = Mock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    acquire_ctx.__aexit__.return_value = False
    pool.acquire.return_value = acquire_ctx
    return pool, conn


def test_query_result_model_serialization() -> None:
    """QueryResult should expose row_count aligned with row payload."""
    result = QueryResult(columns=["id"], rows=[[1]], row_count=1, truncated=False, execution_time_ms=5)
    payload = result.model_dump()
    assert payload["row_count"] == len(payload["rows"])


def test_ensure_limit_adds_limit_when_missing(query_config) -> None:
    """Missing LIMIT should be injected."""
    executor = SQLExecutor(query_config)
    rewritten = executor._ensure_limit_via_ast("SELECT * FROM users", 100)
    assert "LIMIT 100" in rewritten.upper()


def test_ensure_limit_keeps_smaller_existing_limit(query_config) -> None:
    """Smaller existing limit should remain unchanged."""
    executor = SQLExecutor(query_config)
    rewritten = executor._ensure_limit_via_ast("SELECT * FROM users LIMIT 10", 100)
    assert "LIMIT 10" in rewritten.upper()


def test_ensure_limit_reduces_larger_existing_limit(query_config) -> None:
    """Larger existing limit should be reduced to requested limit."""
    executor = SQLExecutor(query_config)
    rewritten = executor._ensure_limit_via_ast("SELECT * FROM users LIMIT 999", 100)
    assert "LIMIT 100" in rewritten.upper()


def test_ensure_limit_fallback_on_parse_error(query_config, monkeypatch: pytest.MonkeyPatch) -> None:
    """Parser failure should use string fallback."""
    executor = SQLExecutor(query_config)

    def _raise_parse_error(*_args, **_kwargs):
        raise ValueError

    monkeypatch.setattr("pg_mcp.services.executor.sqlglot.parse_one", _raise_parse_error)
    rewritten = executor._ensure_limit_via_ast("SELECT * FROM users", 25)
    assert rewritten == "SELECT * FROM users LIMIT 25"


@pytest.mark.asyncio
async def test_initialize_and_close_pools(
    query_config,
    sample_database_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Executor should create and close pools."""
    executor = SQLExecutor(query_config)
    fake_pool = AsyncMock()
    create_pool = AsyncMock(return_value=fake_pool)
    monkeypatch.setattr("pg_mcp.services.executor.asyncpg.create_pool", create_pool)

    await executor.initialize([sample_database_config])
    assert executor.get_pool(sample_database_config.name) is fake_pool
    create_pool.assert_awaited_once()

    await executor.close()
    fake_pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialize_retries_pool_creation_then_succeeds(
    query_config,
    sample_database_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transient connection failures should be retried within bounded attempts."""
    query_config.connect_max_retries = 2
    query_config.connect_retry_base_delay = 0.01
    executor = SQLExecutor(query_config)
    fake_pool = AsyncMock()
    create_pool = AsyncMock(side_effect=[RuntimeError("temporary"), fake_pool])
    sleep = AsyncMock()

    monkeypatch.setattr("pg_mcp.services.executor.asyncpg.create_pool", create_pool)
    monkeypatch.setattr("pg_mcp.services.executor.asyncio.sleep", sleep)

    await executor.initialize([sample_database_config])
    assert executor.get_pool(sample_database_config.name) is fake_pool
    assert create_pool.await_count == 2
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialize_records_unhealthy_database_without_raising(
    query_config,
    sample_database_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed DB init should degrade gracefully and mark DB unhealthy."""
    query_config.connect_max_retries = 0
    executor = SQLExecutor(query_config)
    create_pool = AsyncMock(side_effect=RuntimeError("connection refused"))
    monkeypatch.setattr("pg_mcp.services.executor.asyncpg.create_pool", create_pool)

    await executor.initialize([sample_database_config])

    assert executor.healthy_databases() == []
    assert sample_database_config.name in executor.unhealthy_databases()
    with pytest.raises(DatabaseConnectionError):
        executor.get_pool(sample_database_config.name)


def test_get_pool_raises_for_unknown_db(query_config) -> None:
    """Unknown database should raise DatabaseNotFoundError."""
    executor = SQLExecutor(query_config)
    with pytest.raises(DatabaseNotFoundError):
        executor.get_pool("missing")


@pytest.mark.asyncio
async def test_execute_truncates_rows(query_config) -> None:
    """Executor should fetch limit+1 rows and truncate response payload."""
    executor = SQLExecutor(query_config)
    pool, conn = _make_pool_and_connection(records=[{"id": 1}, {"id": 2}, {"id": 3}])
    executor._pools["default"] = pool

    result = await executor.execute("default", "SELECT id FROM users", limit=2)

    assert result.row_count == 2
    assert result.truncated is True
    assert result.columns == ["id"]
    assert result.rows == [[1], [2]]
    conn.execute.assert_awaited_once_with("SET statement_timeout = '30s'")
    conn.fetch.assert_awaited_once()
    executed_sql = conn.fetch.await_args.args[0]
    assert "LIMIT 3" in executed_sql.upper()


@pytest.mark.asyncio
async def test_execute_maps_query_canceled_to_timeout(query_config) -> None:
    """QueryCanceledError should become domain QueryTimeoutError."""
    executor = SQLExecutor(query_config)
    pool, conn = _make_pool_and_connection(records=[])
    conn.fetch.side_effect = asyncpg.exceptions.QueryCanceledError("statement timeout")
    executor._pools["default"] = pool

    with pytest.raises(QueryTimeoutError):
        await executor.execute("default", "SELECT 1", limit=1)


@pytest.mark.asyncio
async def test_health_check(query_config) -> None:
    """Health check should return True on successful SELECT 1."""
    executor = SQLExecutor(query_config)
    pool, conn = _make_pool_and_connection(records=[])
    executor._pools["default"] = pool

    assert await executor.health_check("default") is True
    conn.fetchval.assert_awaited_once_with("SELECT 1")
