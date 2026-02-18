from __future__ import annotations

from typing import Literal, NoReturn

from fastapi import APIRouter, HTTPException, Path

from src.application.database_orchestrator import (
    DatabaseNotFoundError,
    DatabaseOrchestrator,
    MetadataNotFoundError,
)
from src.infrastructure.registry import build_default_registry
from src.models.error import QueryError
from src.models.query import (
    NaturalQueryPayload,
    NaturalQueryResponse,
    QueryResult,
    SqlQueryPayload,
)
from src.services.connection_service import ConnectionService
from src.services.llm_service import LlmService, LlmServiceError
from src.services.query_service import QueryService, QueryValidationError

router = APIRouter(prefix="/dbs", tags=["queries"])


query_service = QueryService()
registry = build_default_registry()
connection_service = ConnectionService(registry)
llm_service = LlmService()
orchestrator = DatabaseOrchestrator(
    registry=registry,
    connection_service=connection_service,
    query_service=query_service,
    llm_service=llm_service,
)
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
    name: str = Path(pattern=r"^[a-zA-Z0-9_-]+$"),
) -> QueryResult:
    try:
        return orchestrator.execute_sql(name=name, sql=payload.sql)
    except DatabaseNotFoundError as exc:
        _error(
            404,
            error_type="connection",
            error_code="DB_NOT_FOUND",
            message=str(exc),
            query=payload.sql,
        )
    except QueryValidationError as exc:
        _error(
            400,
            error_type="validation",
            error_code="SQL_VALIDATION_FAILED",
            message=str(exc),
            query=payload.sql,
        )
    except Exception as exc:
        _error(
            500,
            error_type="execution",
            error_code="QUERY_EXECUTION_FAILED",
            message="Failed to execute SQL query",
            details=str(exc),
            query=payload.sql,
        )


@router.post("/{name}/query/natural", response_model=NaturalQueryResponse)
def generate_sql_from_natural(
    payload: NaturalQueryPayload,
    name: str = Path(pattern=r"^[a-zA-Z0-9_-]+$"),
) -> NaturalQueryResponse:
    try:
        return orchestrator.generate_sql_from_natural(name=name, prompt=payload.prompt)
    except DatabaseNotFoundError as exc:
        _error(
            404,
            error_type="connection",
            error_code="DB_NOT_FOUND",
            message=str(exc),
        )
    except MetadataNotFoundError as exc:
        _error(
            404,
            error_type="validation",
            error_code="METADATA_NOT_FOUND",
            message=str(exc),
        )
    except LlmServiceError as exc:
        _error(
            500,
            error_type="execution",
            error_code="SQL_GENERATION_FAILED",
            message="Failed to generate SQL from natural language",
            details=str(exc),
        )
    except QueryValidationError as exc:
        _error(
            400,
            error_type="validation",
            error_code="GENERATED_SQL_VALIDATION_FAILED",
            message=str(exc),
            query=payload.prompt,
        )
    except Exception as exc:
        _error(
            500,
            error_type="execution",
            error_code="SQL_GENERATION_FAILED",
            message="Failed to generate SQL from natural language",
            details=str(exc),
        )
