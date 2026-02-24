"""FastMCP server and tool definitions."""

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

mcp = FastMCP("pg-mcp-server")


@mcp.tool()
async def query_database(
    query: str,
    database: str | None = None,
    return_mode: ReturnMode = "both",
    limit: int = 100,
) -> dict:
    """Convert natural-language query to SQL, validate, execute and return response."""
    ctx = get_context()

    try:
        if return_mode not in ("sql", "result", "both"):
            raise InvalidInputError(f"Invalid return_mode: {return_mode}", {"return_mode": return_mode})
        if limit < 1:
            raise InvalidInputError("Limit must be >= 1.", {"limit": limit})

        default_db = ctx.settings.default_database.name if ctx.settings.default_database else None
        db_name = database or default_db
        if not db_name:
            raise DatabaseNotFoundError("default")

        db_config = _get_database_config(ctx, db_name)
        if db_config is None:
            raise DatabaseNotFoundError(db_name)

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
            ).model_dump()

        result_payload: QueryResultData | None = None
        execution_time_ms: int | None = None
        if return_mode in ("result", "both"):
            query_result = await ctx.executor.execute(
                db_name=db_config.name,
                sql=generated_sql,
                limit=min(limit, ctx.settings.query.max_rows_limit),
            )
            result_payload = QueryResultData(**query_result.model_dump())
            execution_time_ms = query_result.execution_time_ms

        response_data = QueryResponseData(
            sql=generated_sql if return_mode in ("sql", "both") else None,
            result=result_payload,
            validation=ValidationInfo(status="passed", confidence=1.0, message=validation_result.message),
            metadata=QueryMetadata(
                database=db_config.name,
                execution_time_ms=execution_time_ms,
            ),
        )
        return QueryResponse(data=response_data).model_dump(mode="json")

    except PgMcpError as exc:
        return ErrorResponse(
            code=exc.code.value,
            message=exc.message,
            details=exc.details,
        ).model_dump()
    except Exception:
        return ErrorResponse(
            code=ErrorCode.QUERY_EXECUTION_ERROR.value,
            message="查询执行过程中发生错误，请稍后重试",
        ).model_dump()


def _get_database_config(ctx, db_name: str):
    """Resolve configured database by name."""
    for db in ctx.settings.databases:
        if db.name == db_name:
            return db
    return None
