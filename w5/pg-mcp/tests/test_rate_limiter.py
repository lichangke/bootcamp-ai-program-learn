"""Tests for in-memory query rate limiter."""

import asyncio

import pytest

from pg_mcp.exceptions.errors import RateLimitExceededError
from pg_mcp.services.rate_limiter import QueryRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_disabled_mode_allows_requests() -> None:
    """Limiter should be a no-op when all limits are disabled."""
    limiter = QueryRateLimiter(max_concurrent_requests=0, rate_limit_per_minute=0)
    assert limiter.enabled is False

    async with limiter.slot():
        assert True


@pytest.mark.asyncio
async def test_rate_limit_per_window_blocks_excess_requests() -> None:
    """Second request in same window should be rejected when threshold is 1."""
    limiter = QueryRateLimiter(rate_limit_per_minute=1, window_seconds=60)
    assert limiter.enabled is True

    async with limiter.slot():
        pass

    with pytest.raises(RateLimitExceededError):
        async with limiter.slot():
            pass


@pytest.mark.asyncio
async def test_concurrency_limit_blocks_parallel_entry() -> None:
    """Concurrency guard should block second request while first slot is held."""
    limiter = QueryRateLimiter(max_concurrent_requests=1)

    async def _enter_once() -> None:
        async with limiter.slot():
            await asyncio.sleep(0.02)

    first = asyncio.create_task(_enter_once())
    await asyncio.sleep(0.005)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(_enter_once(), timeout=0.005)

    await first
