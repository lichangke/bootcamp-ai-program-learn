"""In-memory query rate limiter for MCP tool invocations."""

import asyncio
import time
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pg_mcp.exceptions.errors import RateLimitExceededError


class QueryRateLimiter:
    """Combined concurrency + fixed-window rate limiter."""

    def __init__(
        self,
        max_concurrent_requests: int = 0,
        rate_limit_per_minute: int = 0,
        window_seconds: int = 60,
    ):
        self.max_concurrent_requests = max(0, int(max_concurrent_requests))
        self.rate_limit_per_minute = max(0, int(rate_limit_per_minute))
        self.window_seconds = max(1, int(window_seconds))

        self._semaphore = (
            asyncio.Semaphore(self.max_concurrent_requests) if self.max_concurrent_requests > 0 else None
        )
        self._lock = asyncio.Lock()
        self._request_timestamps: deque[float] = deque()

    @property
    def enabled(self) -> bool:
        """Return whether any limiter mode is enabled."""
        return self.max_concurrent_requests > 0 or self.rate_limit_per_minute > 0

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Acquire one processing slot and enforce request rate limit."""
        acquired = False
        if self._semaphore is not None:
            await self._semaphore.acquire()
            acquired = True

        try:
            await self._check_rate_limit()
            yield
        finally:
            if acquired and self._semaphore is not None:
                self._semaphore.release()

    async def _check_rate_limit(self) -> None:
        """Raise RateLimitExceededError when fixed-window threshold is reached."""
        if self.rate_limit_per_minute <= 0:
            return

        now = time.monotonic()
        cutoff = now - self.window_seconds

        async with self._lock:
            while self._request_timestamps and self._request_timestamps[0] < cutoff:
                self._request_timestamps.popleft()

            current = len(self._request_timestamps)
            if current >= self.rate_limit_per_minute:
                raise RateLimitExceededError(
                    message="Rate limit exceeded, please retry later.",
                    details={
                        "limit": self.rate_limit_per_minute,
                        "window_seconds": self.window_seconds,
                        "current": current,
                    },
                )

            self._request_timestamps.append(now)
