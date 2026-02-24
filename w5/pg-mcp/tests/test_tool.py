"""Tests for query_database MCP tool workflow."""

from unittest.mock import AsyncMock, Mock

import pytest

from pg_mcp.context import AppContext, clear_context, set_context
from pg_mcp.exceptions.errors import ErrorCode, QueryTimeoutError, SQLGenerationError
from pg_mcp.security.validator import ValidationResult
from pg_mcp.server import query_database


@pytest.fixture(autouse=True)
def _cleanup_context() -> None:
    """Ensure tool tests do not share global context state."""
    clear_context()
    yield
    clear_context()


def _build_context(settings_fixture):
    validator = Mock()
    schema_service = AsyncMock()
    executor = Mock()
    executor.execute = AsyncMock()
    executor.close = AsyncMock()
    executor.get_pool.return_value = Mock()
    llm_service = AsyncMock()
    return AppContext(
        settings=settings_fixture,
        validator=validator,
        executor=executor,
        schema_service=schema_service,
        llm_service=llm_service,
    )


@pytest.mark.asyncio
async def test_tool_happy_path_both(settings_fixture) -> None:
    """Tool should return SQL and execution result in `both` mode."""
    ctx = _build_context(settings_fixture)
    ctx.schema_service.get_schema.return_value = Mock()
    ctx.llm_service.generate_sql.return_value = "SELECT id FROM users"
    ctx.validator.validate.return_value = ValidationResult(is_safe=True, message="ok")
    ctx.executor.execute.return_value = Mock(
        model_dump=lambda: {
            "columns": ["id"],
            "rows": [[1]],
            "row_count": 1,
            "truncated": False,
            "execution_time_ms": 5,
        },
        execution_time_ms=5,
    )
    set_context(ctx)

    result = await query_database("show users", return_mode="both")
    assert result["success"] is True
    assert result["data"]["sql"] == "SELECT id FROM users"
    assert result["data"]["result"]["row_count"] == 1


@pytest.mark.asyncio
async def test_tool_return_mode_sql(settings_fixture) -> None:
    """`sql` mode should not execute SQL against DB."""
    ctx = _build_context(settings_fixture)
    ctx.schema_service.get_schema.return_value = Mock()
    ctx.llm_service.generate_sql.return_value = "SELECT 1"
    ctx.validator.validate.return_value = ValidationResult(is_safe=True, message="ok")
    set_context(ctx)

    result = await query_database("show users", return_mode="sql")
    assert result["success"] is True
    assert result["data"]["sql"] == "SELECT 1"
    assert result["data"]["result"] is None
    ctx.executor.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_return_mode_result(settings_fixture) -> None:
    """`result` mode should hide SQL in response payload."""
    ctx = _build_context(settings_fixture)
    ctx.schema_service.get_schema.return_value = Mock()
    ctx.llm_service.generate_sql.return_value = "SELECT id FROM users"
    ctx.validator.validate.return_value = ValidationResult(is_safe=True, message="ok")
    ctx.executor.execute.return_value = Mock(
        model_dump=lambda: {
            "columns": ["id"],
            "rows": [[1]],
            "row_count": 1,
            "truncated": False,
            "execution_time_ms": 5,
        },
        execution_time_ms=5,
    )
    set_context(ctx)

    result = await query_database("show users", return_mode="result")
    assert result["success"] is True
    assert result["data"]["sql"] is None
    assert result["data"]["result"]["row_count"] == 1


@pytest.mark.asyncio
async def test_tool_database_not_found(settings_fixture) -> None:
    """Unknown database should return DB_NOT_FOUND error."""
    ctx = _build_context(settings_fixture)
    set_context(ctx)

    result = await query_database("show users", database="missing")
    assert result["success"] is False
    assert result["error"]["code"] == ErrorCode.DB_NOT_FOUND.value


@pytest.mark.asyncio
async def test_tool_schema_not_ready(settings_fixture) -> None:
    """Missing schema cache should return SCHEMA_NOT_READY."""
    ctx = _build_context(settings_fixture)
    ctx.schema_service.get_schema.return_value = None
    set_context(ctx)

    result = await query_database("show users")
    assert result["success"] is False
    assert result["error"]["code"] == ErrorCode.SCHEMA_NOT_READY.value


@pytest.mark.asyncio
async def test_tool_validation_failure_returns_security_violation(settings_fixture) -> None:
    """Unsafe SQL should return SECURITY_VIOLATION without DB execution."""
    ctx = _build_context(settings_fixture)
    ctx.schema_service.get_schema.return_value = Mock()
    ctx.llm_service.generate_sql.return_value = "DELETE FROM users"
    ctx.validator.validate.return_value = ValidationResult(
        is_safe=False,
        message="unsafe",
        detected_issues=["Delete"],
    )
    set_context(ctx)

    result = await query_database("delete all users")
    assert result["success"] is False
    assert result["error"]["code"] == ErrorCode.SECURITY_VIOLATION.value
    ctx.executor.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_llm_failure(settings_fixture) -> None:
    """LLM failure should map to SQL_GENERATION_ERROR."""
    ctx = _build_context(settings_fixture)
    ctx.schema_service.get_schema.return_value = Mock()
    ctx.llm_service.generate_sql.side_effect = SQLGenerationError("provider timeout")
    set_context(ctx)

    result = await query_database("show users")
    assert result["success"] is False
    assert result["error"]["code"] == ErrorCode.SQL_GENERATION_ERROR.value


@pytest.mark.asyncio
async def test_tool_timeout_failure(settings_fixture) -> None:
    """Executor timeout should map to QUERY_TIMEOUT."""
    ctx = _build_context(settings_fixture)
    ctx.schema_service.get_schema.return_value = Mock()
    ctx.llm_service.generate_sql.return_value = "SELECT * FROM users"
    ctx.validator.validate.return_value = ValidationResult(is_safe=True, message="ok")
    ctx.executor.execute.side_effect = QueryTimeoutError(30)
    set_context(ctx)

    result = await query_database("show users")
    assert result["success"] is False
    assert result["error"]["code"] == ErrorCode.QUERY_TIMEOUT.value


@pytest.mark.asyncio
async def test_tool_unexpected_error_returns_generic(settings_fixture) -> None:
    """Unexpected exceptions should return generic QUERY_EXECUTION_ERROR."""
    ctx = _build_context(settings_fixture)
    ctx.schema_service.get_schema.return_value = Mock()
    ctx.llm_service.generate_sql.return_value = "SELECT * FROM users"
    ctx.validator.validate.return_value = ValidationResult(is_safe=True, message="ok")
    ctx.executor.execute.side_effect = RuntimeError("boom")
    set_context(ctx)

    result = await query_database("show users")
    assert result["success"] is False
    assert result["error"]["code"] == ErrorCode.QUERY_EXECUTION_ERROR.value
