"""FastMCP server and tool definitions."""

import logging
import time
from contextlib import asynccontextmanager, nullcontext
from uuid import uuid4

from fastmcp import FastMCP

from pg_mcp.context import get_context
from pg_mcp.exceptions.errors import (
    DatabaseNotFoundError,
    ErrorCode,
    InvalidInputError,
    PgMcpError,
    SchemaNotReadyError,
)
from pg_mcp.models.request import ReturnMode
from pg_mcp.models.response import (
    ErrorResponse,
    QueryMetadata,
    QueryResponse,
    QueryResponseData,
    QueryResultData,
    ValidationInfo,
)
from pg_mcp.request_context import reset_request_id, set_request_id

logger = logging.getLogger(__name__)
mcp = FastMCP("pg-mcp-server")


@mcp.tool()
async def query_database(
    query: str,
    database: str | None = None,
    return_mode: ReturnMode | None = None,
    limit: int | None = None,
) -> dict:
    """Convert natural-language query to SQL, validate, execute and return response."""
    ctx = get_context()
    request_id = str(uuid4())
    token = set_request_id(request_id)
    started = time.perf_counter()
    resolved_return_mode = return_mode or ctx.settings.query.default_return_mode
    resolved_limit = ctx.settings.query.max_rows if limit is None else limit

    logger.info(
        "query_request_received",
        extra={
            "event": "query_request_received",
            "request_id": request_id,
            "database": database,
            "return_mode": resolved_return_mode,
            "limit": resolved_limit,
            "query_length": len(query or ""),
        },
    )

    try:
        if resolved_return_mode not in ("sql", "result", "both"):
            raise InvalidInputError(
                f"Invalid return_mode: {resolved_return_mode}",
                {"return_mode": resolved_return_mode},
            )
        if resolved_limit < 1:
            raise InvalidInputError("Limit must be >= 1.", {"limit": resolved_limit})

        default_db = ctx.settings.default_database.name if ctx.settings.default_database else None
        db_name = database or default_db
        if not db_name:
            raise DatabaseNotFoundError("default")

        db_config = _get_database_config(ctx, db_name)
        if db_config is None:
            raise DatabaseNotFoundError(db_name)

        limiter_cm = ctx.rate_limiter.slot() if ctx.rate_limiter and ctx.rate_limiter.enabled else nullcontext()
        async with _as_async_context(limiter_cm):
            pool = ctx.executor.get_pool(db_config.name)
            schema_info = await ctx.schema_service.get_schema(db_config.name, pool=pool)
            if schema_info is None:
                raise SchemaNotReadyError(db_config.name)

            generated_sql = await ctx.llm_service.generate_sql(
                natural_query=query,
                schema_info=schema_info,
                dialect="postgres",
            )

            validation_result = ctx.validator.validate(generated_sql)
            if not validation_result.is_safe:
                return ErrorResponse(
                    code=ErrorCode.SECURITY_VIOLATION.value,
                    message=validation_result.message,
                    details={"detected_issues": validation_result.detected_issues},
                    request_id=request_id,
                ).model_dump()

            result_payload: QueryResultData | None = None
            execution_time_ms: int | None = None
            if resolved_return_mode in ("result", "both"):
                query_result = await ctx.executor.execute(
                    db_name=db_config.name,
                    sql=generated_sql,
                    limit=min(resolved_limit, ctx.settings.query.max_rows_limit),
                )
                result_payload = QueryResultData(**query_result.model_dump())
                execution_time_ms = query_result.execution_time_ms

            response_data = QueryResponseData(
                sql=generated_sql if resolved_return_mode in ("sql", "both") else None,
                result=result_payload,
                validation=ValidationInfo(status="passed", confidence=1.0, message=validation_result.message),
                metadata=QueryMetadata(
                    database=db_config.name,
                    execution_time_ms=execution_time_ms,
                ),
            )
            response = QueryResponse(data=response_data, request_id=request_id).model_dump(mode="json")
            logger.info(
                "query_request_succeeded",
                extra={
                    "event": "query_request_succeeded",
                    "request_id": request_id,
                    "database": db_config.name,
                    "return_mode": resolved_return_mode,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                },
            )
            return response

    except PgMcpError as exc:
        logger.warning(
            "query_request_failed",
            extra={
                "event": "query_request_failed",
                "request_id": request_id,
                "error_code": exc.code.value,
                "reason": exc.message,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return ErrorResponse(
            code=exc.code.value,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        ).model_dump()
    except Exception as exc:
        logger.exception(
            "query_request_unexpected_error",
            extra={
                "event": "query_request_unexpected_error",
                "request_id": request_id,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return ErrorResponse(
            code=ErrorCode.QUERY_EXECUTION_ERROR.value,
            message="Query execution failed, please retry later.",
            details={"reason": str(exc)},
            request_id=request_id,
        ).model_dump()
    finally:
        reset_request_id(token)


@asynccontextmanager
async def _as_async_context(cm):
    """Adapt sync/async context managers for unified `async with` usage."""
    if hasattr(cm, "__aenter__"):
        async with cm:
            yield
        return

    with cm:
        yield


def _get_database_config(ctx, db_name: str):
    """Resolve configured database by name."""
    for db in ctx.settings.databases:
        if db.name == db_name:
            return db
    return None
