"""Tests for settings loading and default behavior."""

import pytest
from pydantic import SecretStr, ValidationError

from pg_mcp.config.settings import DatabaseConfig, Settings


def test_settings_defaults_when_minimal_valid_input() -> None:
    """Only deepseek api key is required for a valid settings object."""
    settings = Settings(_env_file=None, deepseek={"api_key": "sk-test"})

    assert settings.server_name == "pg-mcp-server"
    assert settings.log_level == "INFO"
    assert settings.server.transport == "stdio"
    assert settings.server.host == "127.0.0.1"
    assert settings.server.port == 8000
    assert settings.server.path == "/mcp"
    assert settings.query.max_rows == 100
    assert settings.query.connect_max_retries == 2
    assert settings.query.max_concurrent_requests == 0
    assert settings.schema_cache.ttl_minutes == 60
    assert settings.schema_cache.preload_on_startup is False
    assert settings.databases == []


def test_settings_load_from_nested_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings must support nested env variable deserialization."""
    monkeypatch.setenv("DEEPSEEK__API_KEY", "sk-env")
    monkeypatch.setenv("DATABASES__0__NAME", "analytics")
    monkeypatch.setenv("DATABASES__0__HOST", "db.internal")
    monkeypatch.setenv("DATABASES__0__PORT", "5433")
    monkeypatch.setenv("DATABASES__0__DATABASE", "warehouse")
    monkeypatch.setenv("DATABASES__0__USERNAME", "readonly")
    monkeypatch.setenv("DATABASES__0__PASSWORD", "secret")
    monkeypatch.setenv("DATABASES__0__IS_DEFAULT", "true")
    monkeypatch.setenv("SERVER__TRANSPORT", "streamable-http")
    monkeypatch.setenv("SERVER__HOST", "0.0.0.0")
    monkeypatch.setenv("SERVER__PORT", "18000")
    monkeypatch.setenv("SERVER__PATH", "gateway/mcp")

    settings = Settings(_env_file=None)

    assert settings.deepseek.api_key.get_secret_value() == "sk-env"
    assert len(settings.databases) == 1
    assert settings.databases[0].host == "db.internal"
    assert settings.databases[0].port == 5433
    assert settings.default_database is not None
    assert settings.default_database.name == "analytics"
    assert settings.server.transport == "streamable-http"
    assert settings.server.host == "0.0.0.0"
    assert settings.server.port == 18000
    assert settings.server.path == "/gateway/mcp"


def test_secret_str_not_exposed_in_repr() -> None:
    """SecretStr must keep plaintext out of repr output."""
    config = DatabaseConfig(
        name="test",
        database="test",
        username="user",
        password=SecretStr("very-secret"),
    )

    assert "very-secret" not in repr(config)
    assert config.password.get_secret_value() == "very-secret"


def test_missing_required_field_raises_validation_error() -> None:
    """Missing deepseek api key should fail validation."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_default_database_prefers_explicit_default() -> None:
    """default_database should prioritize the entry marked as default."""
    settings = Settings(
        _env_file=None,
        deepseek={"api_key": "sk-test"},
        databases=[
            {
                "name": "db_a",
                "database": "a",
                "username": "u",
                "password": "p",
                "is_default": False,
            },
            {
                "name": "db_b",
                "database": "b",
                "username": "u",
                "password": "p",
                "is_default": True,
            },
        ],
    )

    assert settings.default_database is not None
    assert settings.default_database.name == "db_b"


def test_default_database_falls_back_to_first() -> None:
    """default_database should fall back to first entry when no default flag exists."""
    settings = Settings(
        _env_file=None,
        deepseek={"api_key": "sk-test"},
        databases=[
            {
                "name": "first",
                "database": "a",
                "username": "u",
                "password": "p",
            },
            {
                "name": "second",
                "database": "b",
                "username": "u",
                "password": "p",
            },
        ],
    )

    assert settings.default_database is not None
    assert settings.default_database.name == "first"
