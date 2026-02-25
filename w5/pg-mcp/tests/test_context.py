"""Tests for AppContext global helpers."""

from unittest.mock import AsyncMock, Mock

import pytest

from pg_mcp.context import (
    AppContext,
    clear_context,
    get_context,
    get_request_id,
    reset_request_id,
    set_context,
    set_request_id,
)


@pytest.fixture(autouse=True)
def _cleanup_context() -> None:
    """Ensure tests do not leak global context."""
    clear_context()
    yield
    clear_context()


def test_get_context_raises_when_uninitialized() -> None:
    """get_context should fail before initialization."""
    with pytest.raises(RuntimeError):
        get_context()


def test_set_and_get_context(settings_fixture) -> None:
    """set_context should make object available via get_context."""
    ctx = AppContext(
        settings=settings_fixture,
        validator=Mock(),
        executor=AsyncMock(),
        schema_service=Mock(),
        llm_service=AsyncMock(),
    )
    set_context(ctx)
    assert get_context() is ctx


@pytest.mark.asyncio
async def test_app_context_close_closes_services(settings_fixture) -> None:
    """AppContext.close should close llm and executor in order."""
    executor = AsyncMock()
    llm_service = AsyncMock()
    ctx = AppContext(
        settings=settings_fixture,
        validator=Mock(),
        executor=executor,
        schema_service=Mock(),
        llm_service=llm_service,
    )

    await ctx.close()
    llm_service.close.assert_awaited_once()
    executor.close.assert_awaited_once()


def test_request_id_context_helpers() -> None:
    """set_request_id/reset_request_id should bind and restore request scope."""
    assert get_request_id() is None
    token = set_request_id("req-xyz")
    assert get_request_id() == "req-xyz"
    reset_request_id(token)
    assert get_request_id() is None
