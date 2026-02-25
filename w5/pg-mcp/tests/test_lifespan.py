"""Tests for application lifespan initialization and cleanup."""

from unittest.mock import AsyncMock, Mock

import pytest

from pg_mcp.context import clear_context, get_context


@pytest.fixture(autouse=True)
def _cleanup_context() -> None:
    """Reset global context before and after each test."""
    clear_context()
    yield
    clear_context()


@pytest.mark.asyncio
async def test_lifespan_initializes_and_closes(monkeypatch: pytest.MonkeyPatch, settings_fixture) -> None:
    """Normal lifespan should initialize services and close resources."""
    import pg_mcp.__main__ as main_module

    validator = Mock()
    executor = Mock()
    executor.initialize = AsyncMock()
    executor.close = AsyncMock()
    executor.get_pool.return_value = Mock()
    executor.healthy_databases.return_value = ["default"]
    executor.unhealthy_databases.return_value = {}
    schema_service = Mock()
    schema_service.discover = AsyncMock()
    llm_service = Mock()
    llm_service.close = AsyncMock()

    monkeypatch.setattr(main_module, "Settings", lambda: settings_fixture)
    monkeypatch.setattr(main_module, "SQLValidator", lambda _cfg: validator)
    monkeypatch.setattr(main_module, "SQLExecutor", lambda _cfg: executor)
    monkeypatch.setattr(main_module, "SchemaService", lambda _cfg: schema_service)
    monkeypatch.setattr(main_module, "LLMService", lambda _cfg, _svc: llm_service)

    async with main_module.app_lifespan(None):
        ctx = get_context()
        assert ctx.settings == settings_fixture
        assert ctx.validator is validator
        executor.initialize.assert_awaited_once()
        schema_service.discover.assert_not_awaited()

    llm_service.close.assert_awaited_once()
    executor.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_cleanup_on_start_failure(monkeypatch: pytest.MonkeyPatch, settings_fixture) -> None:
    """If startup fails midway, already-created resources should still close."""
    import pg_mcp.__main__ as main_module

    settings_fixture.schema_cache.preload_on_startup = True

    executor = Mock()
    executor.initialize = AsyncMock()
    executor.close = AsyncMock()
    executor.get_pool.return_value = Mock()
    executor.healthy_databases.return_value = ["default"]
    executor.unhealthy_databases.return_value = {}
    schema_service = Mock()
    schema_service.discover = AsyncMock(side_effect=RuntimeError("discover failed"))

    monkeypatch.setattr(main_module, "Settings", lambda: settings_fixture)
    monkeypatch.setattr(main_module, "SQLValidator", lambda _cfg: Mock())
    monkeypatch.setattr(main_module, "SQLExecutor", lambda _cfg: executor)
    monkeypatch.setattr(main_module, "SchemaService", lambda _cfg: schema_service)

    with pytest.raises(RuntimeError, match="discover failed"):
        async with main_module.app_lifespan(None):
            pass

    executor.close.assert_awaited_once()
    with pytest.raises(RuntimeError):
        get_context()
