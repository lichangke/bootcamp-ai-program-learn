"""Read-only SQL executor built on asyncpg pools."""

import asyncio
import logging
import random
from datetime import UTC, datetime
from urllib.parse import quote_plus

import asyncpg
import sqlglot
from pydantic import BaseModel
from sqlglot import exp

from pg_mcp.config.settings import DatabaseConfig, QueryConfig
from pg_mcp.exceptions.errors import (
    DatabaseConnectionError,
    DatabaseNotFoundError,
    QueryExecutionError,
    QueryTimeoutError,
)
from pg_mcp.request_context import get_request_id

logger = logging.getLogger(__name__)


class QueryResult(BaseModel):
    """Structured SQL execution result."""

    columns: list[str]
    rows: list[list]
    row_count: int
    truncated: bool
    execution_time_ms: int


class SQLExecutor:
    """Execute validated SQL in read-only PostgreSQL sessions."""

    def __init__(self, query_config: QueryConfig):
        self.query_config = query_config
        self._pools: dict[str, asyncpg.Pool] = {}
        self._failed_pools: dict[str, str] = {}

    async def initialize(self, databases: list[DatabaseConfig]) -> None:
        """Create one asyncpg pool for each configured database with bounded retries."""
        for db_config in databases:
            try:
                pool = await self._create_pool_with_retry(db_config)
            except Exception as exc:
                reason = str(exc)
                self._failed_pools[db_config.name] = reason
                logger.error(
                    "db_pool_init_failed",
                    extra={
                        "event": "db_pool_init_failed",
                        "database": db_config.name,
                        "reason": reason,
                    },
                )
                continue

            self._pools[db_config.name] = pool
            self._failed_pools.pop(db_config.name, None)
            logger.info(
                "db_pool_init_ok",
                extra={
                    "event": "db_pool_init_ok",
                    "database": db_config.name,
                },
            )

    def get_pool(self, db_name: str) -> asyncpg.Pool:
        """Return pool by configured database name."""
        pool = self._pools.get(db_name)
        if pool is None:
            if db_name in self._failed_pools:
                raise DatabaseConnectionError(db_name, self._failed_pools[db_name])
            raise DatabaseNotFoundError(db_name)
        return pool

    async def execute(self, db_name: str, sql: str, limit: int) -> QueryResult:
        """Execute SQL with timeout, limit guard and truncation detection."""
        request_id = get_request_id()
        pool = self.get_pool(db_name)
        effective_limit = max(1, limit)
        fetch_limit = effective_limit + 1
        protected_sql = self._ensure_limit_via_ast(sql=sql, limit=fetch_limit)
        logger.info(
            "db_query_start",
            extra={
                "event": "db_query_start",
                "request_id": request_id,
                "database": db_name,
                "limit": effective_limit,
            },
        )

        started_at = datetime.now(UTC)
        try:
            async with pool.acquire() as conn:
                await conn.execute(f"SET statement_timeout = '{self.query_config.timeout_seconds}s'")
                records = await conn.fetch(protected_sql)
        except asyncpg.exceptions.QueryCanceledError as exc:
            logger.warning(
                "db_query_timeout",
                extra={
                    "event": "db_query_timeout",
                    "request_id": request_id,
                    "database": db_name,
                    "timeout_seconds": self.query_config.timeout_seconds,
                },
            )
            raise QueryTimeoutError(self.query_config.timeout_seconds) from exc
        except Exception as exc:
            logger.error(
                "db_query_error",
                extra={
                    "event": "db_query_error",
                    "request_id": request_id,
                    "database": db_name,
                    "reason": str(exc),
                },
            )
            raise QueryExecutionError(str(exc)) from exc

        rows_raw = [dict(record) for record in records]
        truncated = len(rows_raw) > effective_limit
        rows_raw = rows_raw[:effective_limit]

        columns = list(rows_raw[0].keys()) if rows_raw else []
        rows: list[list] = [[record.get(column) for column in columns] for record in rows_raw]

        elapsed = datetime.now(UTC) - started_at
        elapsed_ms = int(elapsed.total_seconds() * 1000)
        logger.info(
            "db_query_success",
            extra={
                "event": "db_query_success",
                "request_id": request_id,
                "database": db_name,
                "row_count": len(rows),
                "truncated": truncated,
                "execution_time_ms": elapsed_ms,
            },
        )

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            execution_time_ms=elapsed_ms,
        )

    def _ensure_limit_via_ast(self, sql: str, limit: int) -> str:
        """Apply LIMIT with AST rewrite; fall back to safe string append."""
        try:
            statement = sqlglot.parse_one(sql, dialect="postgres")
            parsed_limit = self._extract_limit(statement)
            final_limit = min(parsed_limit, limit) if parsed_limit is not None else limit
            statement = statement.limit(final_limit)
            return statement.sql(dialect="postgres")
        except Exception:
            normalized_sql = sql.strip().rstrip(";")
            return f"{normalized_sql} LIMIT {limit}"

    async def health_check(self, db_name: str) -> bool:
        """Run lightweight health query against the selected pool."""
        try:
            pool = self.get_pool(db_name)
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False

    def healthy_databases(self) -> list[str]:
        """Return currently initialized healthy database names."""
        return sorted(self._pools.keys())

    def unhealthy_databases(self) -> dict[str, str]:
        """Return databases that failed to initialize and failure reasons."""
        return dict(self._failed_pools)

    async def close(self) -> None:
        """Close all pools."""
        for pool in self._pools.values():
            await pool.close()
        self._pools.clear()
        self._failed_pools.clear()

    @staticmethod
    def _build_dsn(db_config: DatabaseConfig) -> str:
        """Build PostgreSQL DSN with sslmode from typed config."""
        user = quote_plus(db_config.username)
        password = quote_plus(db_config.password.get_secret_value())
        database = quote_plus(db_config.database)
        return (
            f"postgresql://{user}:{password}@{db_config.host}:{db_config.port}/{database}"
            f"?sslmode={quote_plus(db_config.ssl_mode)}"
        )

    async def _create_pool_with_retry(self, db_config: DatabaseConfig) -> asyncpg.Pool:
        """Create one pool with exponential backoff retries."""
        dsn = self._build_dsn(db_config)
        max_retries = max(0, self.query_config.connect_max_retries)
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                return await asyncpg.create_pool(
                    dsn=dsn,
                    min_size=db_config.min_connections,
                    max_size=db_config.max_connections,
                    server_settings={"default_transaction_read_only": "on"},
                )
            except Exception as exc:
                last_error = exc
                if attempt >= max_retries:
                    break
                delay = self._connect_backoff(attempt)
                logger.warning(
                    "db_pool_connect_retry",
                    extra={
                        "event": "db_pool_connect_retry",
                        "database": db_config.name,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "delay_seconds": round(delay, 3),
                        "reason": str(exc),
                    },
                )
                await asyncio.sleep(delay)

        raise DatabaseConnectionError(db_config.name, str(last_error))

    def _connect_backoff(self, attempt: int) -> float:
        """Compute retry delay with jitter for DB connection attempts."""
        base = max(0.0, self.query_config.connect_retry_base_delay)
        delay = base * (2**attempt)
        jitter = 1 + random.uniform(-0.25, 0.25)
        return max(0.0, delay * jitter)

    @staticmethod
    def _extract_limit(statement: exp.Expression) -> int | None:
        """Extract integer literal LIMIT when present."""
        limit_clause = statement.args.get("limit")
        if limit_clause is None:
            return None

        value_expr = getattr(limit_clause, "expression", None)
        if isinstance(value_expr, exp.Literal) and value_expr.is_int:
            return int(value_expr.this)

        return None
