from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, NoReturn

from fastapi import APIRouter, HTTPException, Path

from src.models.error import QueryError
from src.models.metadata import TableMetadata
from src.models.query import (
    NaturalLanguageContext,
    NaturalQueryPayload,
    NaturalQueryResponse,
    QueryResult,
    SqlQueryPayload,
)
from src.services.connection_service import ConnectionService
from src.services.llm_service import LlmService, LlmServiceError
from src.services.query_service import QueryService, QueryValidationError
from src.storage.sqlite_store import get_connection_by_name, get_metadata

router = APIRouter(prefix="/dbs", tags=["queries"])


query_service = QueryService()
connection_service = ConnectionService()
llm_service = LlmService()
QueryErrorType = Literal["connection", "syntax", "validation", "execution", "timeout"]


def _error(
    status_code: int,
    *,
    error_type: QueryErrorType,
    error_code: str,
    message: str,
    details: str | None = None,
    query: str | None = None,
) -> NoReturn:
    payload = QueryError(
        error_type=error_type,
        error_code=error_code,
        message=message,
        details=details,
        query=query,
    )
    raise HTTPException(status_code=status_code, detail=payload.model_dump(by_alias=True))


@router.post("/{name}/query", response_model=QueryResult)
def run_query(
    payload: SqlQueryPayload,
    name: str = Path(pattern=r"^[a-zA-Z0-9-]+$"),
) -> QueryResult:
    connection = get_connection_by_name(name)
    if connection is None:
        _error(
            404,
            error_type="connection",
            error_code="DB_NOT_FOUND",
            message=f"Database connection '{name}' not found",
            query=payload.sql,
        )

    connection_model = connection

    try:
        validated_sql = query_service.validate_sql(payload.sql)
    except QueryValidationError as exc:
        _error(
            400,
            error_type="validation",
            error_code="SQL_VALIDATION_FAILED",
            message=str(exc),
            query=payload.sql,
        )

    try:
        with connection_service.connect(connection_model.url) as conn:
            return query_service.execute_query(conn, validated_sql)
    except Exception as exc:
        _error(
            500,
            error_type="execution",
            error_code="QUERY_EXECUTION_FAILED",
            message="Failed to execute SQL query",
            details=str(exc),
            query=validated_sql,
        )


@router.post("/{name}/query/natural", response_model=NaturalQueryResponse)
def generate_sql_from_natural(
    payload: NaturalQueryPayload,
    name: str = Path(pattern=r"^[a-zA-Z0-9-]+$"),
) -> NaturalQueryResponse:
    connection = get_connection_by_name(name)
    if connection is None:
        _error(
            404,
            error_type="connection",
            error_code="DB_NOT_FOUND",
            message=f"Database connection '{name}' not found",
        )

    metadata = get_metadata(name)
    if metadata is None:
        _error(
            404,
            error_type="validation",
            error_code="METADATA_NOT_FOUND",
            message=f"Metadata for '{name}' not found",
        )

    metadata_model = metadata

    try:
        limited_tables, schema_context, prompt_schema = llm_service.prepare_schema_context(
            metadata_model,
            payload.prompt,
        )
    except Exception as exc:
        _error(
            500,
            error_type="execution",
            error_code="SCHEMA_CONTEXT_PREPARATION_FAILED",
            message="Failed to prepare schema context",
            details=str(exc),
        )

    try:
        generated_sql = llm_service.generate_sql(
            prompt=payload.prompt,
            connection_name=name,
            schema_prompt_context=prompt_schema,
        )
    except LlmServiceError as exc:
        _error(
            500,
            error_type="execution",
            error_code="SQL_GENERATION_FAILED",
            message="Failed to generate SQL from natural language",
            details=str(exc),
        )

    try:
        validated_sql = query_service.validate_sql(generated_sql)
    except QueryValidationError as exc:
        _error(
            400,
            error_type="validation",
            error_code="GENERATED_SQL_VALIDATION_FAILED",
            message=str(exc),
            query=generated_sql,
        )

    typed_context: dict[str, TableMetadata] = schema_context

    context = NaturalLanguageContext(
        connection_name=name,
        user_prompt=payload.prompt,
        relevant_tables=limited_tables,
        schema_context=typed_context,
        generated_sql=validated_sql,
        timestamp=datetime.now(UTC),
    )

    return NaturalQueryResponse(generated_sql=validated_sql, context=context)
