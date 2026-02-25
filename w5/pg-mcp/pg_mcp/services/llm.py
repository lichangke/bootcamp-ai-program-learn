"""DeepSeek LLM service for natural-language-to-SQL generation."""

import asyncio
import logging
import random
import re

import httpx

from pg_mcp.config.settings import DeepSeekConfig
from pg_mcp.exceptions.errors import SQLGenerationError
from pg_mcp.models.schema import SchemaInfo
from pg_mcp.request_context import get_request_id
from pg_mcp.services.schema import SchemaService

SYSTEM_PROMPT = """你是一个 PostgreSQL SQL 专家。
请根据用户的自然语言问题和数据库 Schema 信息生成 SQL。
规则：
1. 仅允许生成 SELECT 查询
2. 使用标准 PostgreSQL 语法
3. 只返回 SQL 本文，不要 markdown 或解释
4. 如果用户意图是写操作，返回以 ERROR: 开头的错误文本
"""

logger = logging.getLogger(__name__)


class LLMService:
    """DeepSeek API client with retry and SQL post-processing."""

    def __init__(self, config: DeepSeekConfig, schema_service: SchemaService):
        self.config = config
        self.schema_service = schema_service
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={
                "Authorization": f"Bearer {config.api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
        )

    async def generate_sql(self, natural_query: str, schema_info: SchemaInfo, dialect: str = "postgres") -> str:
        """Generate SQL from natural-language query and discovered schema."""
        request_id = get_request_id()
        logger.info(
            "llm_generate_start",
            extra={
                "event": "llm_generate_start",
                "request_id": request_id,
                "database": schema_info.database,
                "query_length": len(natural_query),
            },
        )

        schema_text = self.schema_service.format_for_llm(schema_info)
        user_message = self._build_user_message(natural_query=natural_query, schema_text=schema_text, dialect=dialect)
        raw = await self._call_api_with_retry(user_message=user_message)
        sql = self._clean_sql_response(raw)

        logger.info(
            "llm_generate_success",
            extra={
                "event": "llm_generate_success",
                "request_id": request_id,
                "database": schema_info.database,
                "sql_length": len(sql),
            },
        )
        return sql

    async def _call_api_with_retry(self, user_message: str) -> str:
        """Call DeepSeek with exponential-backoff retries for transient failures."""
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                response = await self._client.post(
                    "/chat/completions",
                    json={
                        "model": self.config.model,
                        "temperature": self.config.temperature,
                        "max_tokens": self.config.max_tokens,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_message},
                        ],
                    },
                )
                status_code = response.status_code

                if status_code >= 400:
                    if self._is_retryable_status(status_code) and attempt < self.config.max_retries:
                        logger.warning(
                            "llm_retry_status",
                            extra={
                                "event": "llm_retry_status",
                                "request_id": get_request_id(),
                                "attempt": attempt + 1,
                                "max_retries": self.config.max_retries,
                                "status_code": status_code,
                            },
                        )
                        await asyncio.sleep(self._exponential_backoff(attempt))
                        continue
                    raise SQLGenerationError(f"DeepSeek API request failed with status {status_code}.")

                payload = response.json()
                choices = payload.get("choices") or []
                if not choices:
                    raise SQLGenerationError("DeepSeek API response does not include choices.")
                message = choices[0].get("message") or {}
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise SQLGenerationError("DeepSeek API response content is empty.")
                return content

            except SQLGenerationError as exc:
                last_error = exc
                break
            except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError) as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
                logger.warning(
                    "llm_retry_transport",
                    extra={
                        "event": "llm_retry_transport",
                        "request_id": get_request_id(),
                        "attempt": attempt + 1,
                        "max_retries": self.config.max_retries,
                        "reason": str(exc),
                    },
                )
                await asyncio.sleep(self._exponential_backoff(attempt))
            except Exception as exc:
                last_error = exc
                break

        logger.error(
            "llm_generate_failed",
            extra={
                "event": "llm_generate_failed",
                "request_id": get_request_id(),
                "reason": str(last_error) if last_error else "unknown",
            },
        )
        raise SQLGenerationError(str(last_error) if last_error else "Unknown LLM failure.")

    def _exponential_backoff(self, attempt: int) -> float:
        """Compute retry delay using base * 2^attempt with +/-25% jitter."""
        base_delay = self.config.retry_base_delay * (2**attempt)
        jitter_factor = 1 + random.uniform(-0.25, 0.25)
        return max(0.0, base_delay * jitter_factor)

    def _clean_sql_response(self, response_text: str) -> str:
        """Extract pure SQL from model response and enforce read-only rejection semantics."""
        cleaned = response_text.strip()
        cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        if not cleaned:
            raise SQLGenerationError("LLM returned empty SQL.")
        if cleaned.upper().startswith("ERROR:"):
            raise SQLGenerationError(cleaned)
        return cleaned

    async def close(self) -> None:
        """Close underlying HTTP client."""
        await self._client.aclose()

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        """Return whether status code is retryable."""
        return status_code == 429 or 500 <= status_code < 600

    @staticmethod
    def _build_user_message(natural_query: str, schema_text: str, dialect: str) -> str:
        """Build final user prompt including schema context and SQL dialect."""
        return (
            "Database schema information:\n"
            f"{schema_text}\n\n"
            f"SQL dialect: {dialect}\n"
            f"User query: {natural_query}\n\n"
            "Please generate the corresponding SQL query."
        )
