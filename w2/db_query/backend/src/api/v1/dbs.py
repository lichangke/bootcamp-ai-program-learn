from __future__ import annotations

from typing import Literal, NoReturn

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from src.application.database_orchestrator import (
    DatabaseNotFoundError,
    DatabaseOrchestrator,
    MetadataNotFoundError,
)
from src.infrastructure.registry import build_default_registry
from src.models.connection import DatabaseConnection
from src.models.error import QueryError
from src.models.metadata import SchemaMetadata
from src.services.connection_service import ConnectionService, ConnectionValidationError
from src.services.llm_service import LlmService
from src.services.query_service import QueryService

router = APIRouter(prefix="/dbs", tags=["databases"])


ErrorType = Literal["connection", "syntax", "validation", "execution", "timeout"]


class ConnectionUpsertRequest(BaseModel):
    url: str = Field(
        min_length=1,
        description="Database connection URL (PostgreSQL or MySQL)",
    )


class DatabaseDetailResponse(BaseModel):
    connection: DatabaseConnection
    metadata: SchemaMetadata


registry = build_default_registry()
connection_service = ConnectionService(registry)
query_service = QueryService()
llm_service = LlmService()
orchestrator = DatabaseOrchestrator(
    registry=registry,
    connection_service=connection_service,
    query_service=query_service,
    llm_service=llm_service,
)


def _error(
    status_code: int,
    *,
    error_type: ErrorType = "connection",
    error_code: str,
    message: str,
    details: str | None = None,
) -> NoReturn:
    payload = QueryError(
        error_type=error_type,
        error_code=error_code,
        message=message,
        details=details,
    )
    raise HTTPException(status_code=status_code, detail=payload.model_dump(by_alias=True))


@router.get("", response_model=list[DatabaseConnection])
def get_dbs() -> list[DatabaseConnection]:
    return orchestrator.list_connections()


@router.put("/{name}", response_model=DatabaseConnection)
def put_db(
    request: ConnectionUpsertRequest,
    name: str = Path(pattern=r"^[a-zA-Z0-9_-]+$"),
) -> DatabaseConnection:
    try:
        return orchestrator.upsert_connection_and_metadata(name=name, url=request.url)
    except ConnectionValidationError as exc:
        _error(400, error_code="CONNECTION_VALIDATION_FAILED", message=str(exc))
    except Exception as exc:
        _error(
            500,
            error_code="METADATA_FETCH_FAILED",
            message="Failed to fetch metadata",
            details=str(exc),
        )


@router.get("/{name}", response_model=DatabaseDetailResponse)
def get_db(name: str = Path(pattern=r"^[a-zA-Z0-9_-]+$")) -> DatabaseDetailResponse:
    try:
        connection, metadata = orchestrator.get_database_detail(name)
        return DatabaseDetailResponse(connection=connection, metadata=metadata)
    except DatabaseNotFoundError as exc:
        _error(404, error_code="DB_NOT_FOUND", message=str(exc))
    except MetadataNotFoundError as exc:
        _error(404, error_code="METADATA_NOT_FOUND", message=str(exc))


@router.post("/{name}/refresh", response_model=SchemaMetadata)
def refresh_db(name: str = Path(pattern=r"^[a-zA-Z0-9_-]+$")) -> SchemaMetadata:
    try:
        return orchestrator.refresh_metadata(name)
    except DatabaseNotFoundError as exc:
        _error(404, error_code="DB_NOT_FOUND", message=str(exc))
    except Exception as exc:
        _error(
            500,
            error_code="METADATA_REFRESH_FAILED",
            message="Failed to refresh metadata",
            details=str(exc),
        )


@router.delete("/{name}", status_code=204)
def delete_db(name: str = Path(pattern=r"^[a-zA-Z0-9_-]+$")) -> None:
    try:
        orchestrator.delete_connection(name)
    except DatabaseNotFoundError as exc:
        _error(404, error_code="DB_NOT_FOUND", message=str(exc))
