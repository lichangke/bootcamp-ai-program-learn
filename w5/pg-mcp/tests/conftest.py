"""Shared pytest fixtures."""

import pytest
from pydantic import SecretStr

from pg_mcp.config.settings import DatabaseConfig, QueryConfig, SchemaCacheConfig, SecurityConfig


@pytest.fixture
def sample_database_config() -> DatabaseConfig:
    """Reusable database configuration fixture."""
    return DatabaseConfig(
        name="default",
        host="localhost",
        port=5432,
        database="app",
        username="readonly",
        password=SecretStr("readonly-secret"),
        min_connections=1,
        max_connections=5,
        is_default=True,
    )


@pytest.fixture
def query_config() -> QueryConfig:
    """Default query config for tests."""
    return QueryConfig(timeout_seconds=30, max_rows=100, max_rows_limit=1000, default_return_mode="both")


@pytest.fixture
def schema_cache_config() -> SchemaCacheConfig:
    """Default cache config for schema tests."""
    return SchemaCacheConfig(ttl_minutes=60, auto_refresh=True)


@pytest.fixture
def security_config() -> SecurityConfig:
    """Default security config for validator tests."""
    return SecurityConfig()

