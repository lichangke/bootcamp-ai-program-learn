"""DeepSeek LLM service for natural-language-to-SQL generation."""

import asyncio
import random
import re

import httpx

from pg_mcp.config.settings import DeepSeekConfig
from pg_mcp.exceptions.errors import SQLGenerationError
from pg_mcp.models.schema import SchemaInfo
from pg_mcp.services.schema import SchemaService

SYSTEM_PROMPT = """你是一个 PostgreSQL SQL 专家。根据用户的自然语言描述和数据库 Schema 信息，生成对应的 SQL 查询语句。
规则：
1. 只生成 SELECT 查询语句，禁止任何数据修改操作
2. 使用标准 PostgreSQL 语法
3. 只返回 SQL 语句，不要包含任何解释或 markdown 格式
4. 如果用户请求涉及数据修改，返回 "ERROR: 仅支持查询操作"
5. 合理使用 JOIN、GROUP BY、ORDER BY 等子句
6. 对于模糊的查询，做出合理的假设并生成 SQL"""


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
        schema_text = self.schema_service.format_for_llm(schema_info)
        user_message = self._build_user_message(natural_query=natural_query, schema_text=schema_text, dialect=dialect)
        raw = await self._call_api_with_retry(user_message=user_message)
        return self._clean_sql_response(raw)

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
                await asyncio.sleep(self._exponential_backoff(attempt))
            except Exception as exc:
                last_error = exc
                break

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
            "数据库 Schema 信息：\n"
            f"{schema_text}\n\n"
            f"SQL 方言：{dialect}\n"
            f"用户查询：{natural_query}\n\n"
            "请生成对应的 SQL 查询语句："
        )

