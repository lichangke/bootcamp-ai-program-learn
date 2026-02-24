"""Tests for DeepSeek-backed LLM service."""

from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import SecretStr

from pg_mcp.config.settings import DeepSeekConfig, SchemaCacheConfig
from pg_mcp.exceptions.errors import SQLGenerationError
from pg_mcp.models.schema import SchemaInfo
from pg_mcp.services.llm import LLMService
from pg_mcp.services.schema import SchemaService


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def llm_config() -> DeepSeekConfig:
    """LLM config fixture."""
    return DeepSeekConfig(
        api_key=SecretStr("sk-test"),
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        temperature=0.1,
        max_tokens=1024,
        timeout_seconds=3,
        max_retries=2,
        retry_base_delay=0.01,
    )


@pytest.fixture
def schema_service() -> SchemaService:
    """Schema service fixture for LLM prompt formatting."""
    return SchemaService(SchemaCacheConfig(ttl_minutes=60, auto_refresh=True))


@pytest.fixture
def schema_info() -> SchemaInfo:
    """Simple schema fixture."""
    return SchemaInfo(database="analytics", tables=[])


@pytest.mark.asyncio
async def test_generate_sql_success(
    llm_config: DeepSeekConfig,
    schema_service: SchemaService,
    schema_info: SchemaInfo,
) -> None:
    """LLM service should return SQL content from successful response."""
    service = LLMService(llm_config, schema_service)
    service._client = AsyncMock()
    service._client.post.return_value = _FakeResponse(
        200,
        {"choices": [{"message": {"content": "SELECT * FROM users"}}]},
    )

    sql = await service.generate_sql("show users", schema_info)
    assert sql == "SELECT * FROM users"


@pytest.mark.asyncio
async def test_clean_markdown_sql_blocks(
    llm_config: DeepSeekConfig,
    schema_service: SchemaService,
    schema_info: SchemaInfo,
) -> None:
    """LLM response with markdown code fences should be normalized."""
    service = LLMService(llm_config, schema_service)
    service._client = AsyncMock()
    service._client.post.return_value = _FakeResponse(
        200,
        {"choices": [{"message": {"content": "```sql\nSELECT 1;\n```"}}]},
    )

    sql = await service.generate_sql("test", schema_info)
    assert sql == "SELECT 1;"


@pytest.mark.asyncio
async def test_retry_on_429_then_success(
    llm_config: DeepSeekConfig,
    schema_service: SchemaService,
    schema_info: SchemaInfo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """429 responses should be retried."""
    service = LLMService(llm_config, schema_service)
    service._client = AsyncMock()
    service._client.post.side_effect = [
        _FakeResponse(429, {"error": "rate limit"}),
        _FakeResponse(200, {"choices": [{"message": {"content": "SELECT 1"}}]}),
    ]
    sleep = AsyncMock()
    monkeypatch.setattr("pg_mcp.services.llm.asyncio.sleep", sleep)

    sql = await service.generate_sql("test", schema_info)
    assert sql == "SELECT 1"
    assert service._client.post.await_count == 2
    sleep.assert_awaited()


@pytest.mark.asyncio
async def test_retry_exhausted_500_raises(
    llm_config: DeepSeekConfig,
    schema_service: SchemaService,
    schema_info: SchemaInfo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated 5xx responses should raise SQLGenerationError after retries."""
    service = LLMService(llm_config, schema_service)
    service._client = AsyncMock()
    service._client.post.side_effect = [
        _FakeResponse(500, {"error": "server"}),
        _FakeResponse(500, {"error": "server"}),
        _FakeResponse(500, {"error": "server"}),
    ]
    monkeypatch.setattr("pg_mcp.services.llm.asyncio.sleep", AsyncMock())

    with pytest.raises(SQLGenerationError):
        await service.generate_sql("test", schema_info)
    assert service._client.post.await_count == 3


@pytest.mark.asyncio
async def test_non_retryable_401_fails_fast(
    llm_config: DeepSeekConfig,
    schema_service: SchemaService,
    schema_info: SchemaInfo,
) -> None:
    """4xx non-429 errors should not be retried."""
    service = LLMService(llm_config, schema_service)
    service._client = AsyncMock()
    service._client.post.return_value = _FakeResponse(401, {"error": "unauthorized"})

    with pytest.raises(SQLGenerationError):
        await service.generate_sql("test", schema_info)
    assert service._client.post.await_count == 1


@pytest.mark.asyncio
async def test_timeout_retries_then_success(
    llm_config: DeepSeekConfig,
    schema_service: SchemaService,
    schema_info: SchemaInfo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeout exceptions should trigger retry."""
    service = LLMService(llm_config, schema_service)
    service._client = AsyncMock()
    service._client.post.side_effect = [
        httpx.TimeoutException("timeout"),
        _FakeResponse(200, {"choices": [{"message": {"content": "SELECT 2"}}]}),
    ]
    sleep = AsyncMock()
    monkeypatch.setattr("pg_mcp.services.llm.asyncio.sleep", sleep)

    sql = await service.generate_sql("test", schema_info)
    assert sql == "SELECT 2"
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_calls_http_client_aclose(llm_config: DeepSeekConfig, schema_service: SchemaService) -> None:
    """close should forward to httpx.AsyncClient.aclose."""
    service = LLMService(llm_config, schema_service)
    service._client = AsyncMock()

    await service.close()
    service._client.aclose.assert_awaited_once()
