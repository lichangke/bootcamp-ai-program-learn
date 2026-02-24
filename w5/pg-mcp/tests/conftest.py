"""Shared pytest fixtures."""

import pytest
from pydantic import SecretStr

from pg_mcp.config.settings import (
    DatabaseConfig,
    DeepSeekConfig,
    QueryConfig,
    SchemaCacheConfig,
    SecurityConfig,
    Settings,
)


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


@pytest.fixture
def deepseek_config() -> DeepSeekConfig:
    """Default deepseek config for tests."""
    return DeepSeekConfig(api_key=SecretStr("sk-test"))


@pytest.fixture
def settings_fixture(sample_database_config: DatabaseConfig) -> Settings:
    """Reusable full settings object."""
    return Settings(
        _env_file=None,
        deepseek={"api_key": "sk-test"},
        databases=[sample_database_config.model_dump(mode="json")],
    )
