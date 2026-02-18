from __future__ import annotations

from typing import Literal, NoReturn

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from src.models.connection import DatabaseConnection
from src.models.error import QueryError
from src.models.metadata import SchemaMetadata
from src.services.connection_service import ConnectionService, ConnectionValidationError
from src.services.metadata_service import MetadataService
from src.storage.sqlite_store import (
    delete_connection,
    get_connection_by_name,
    get_metadata,
    list_connections,
    save_metadata,
    upsert_connection,
)

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


connection_service = ConnectionService()
metadata_service = MetadataService()


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
    return list_connections()


@router.put("/{name}", response_model=DatabaseConnection)
def put_db(
    request: ConnectionUpsertRequest,
    name: str = Path(pattern=r"^[a-zA-Z0-9-]+$"),
) -> DatabaseConnection:
    request_model = request
    try:
        connection_service.test_connection(request_model.url)
    except ConnectionValidationError as exc:
        _error(400, error_code="CONNECTION_VALIDATION_FAILED", message=str(exc))

    existing = get_connection_by_name(name)
    model = connection_service.create_connection_model(
        name=name,
        url=request_model.url,
        existing=existing,
    )
    upsert_connection(model)

    try:
        with connection_service.connect(model.url) as conn:
            dialect = connection_service.detect_dialect(model.url)
            metadata = metadata_service.fetch_metadata(name, conn, dialect)
        save_metadata(name, metadata)
    except Exception as exc:
        _error(
            500,
            error_code="METADATA_FETCH_FAILED",
            message="Failed to fetch metadata",
            details=str(exc),
        )

    return model


@router.get("/{name}", response_model=DatabaseDetailResponse)
def get_db(name: str = Path(pattern=r"^[a-zA-Z0-9-]+$")) -> DatabaseDetailResponse:
    connection = get_connection_by_name(name)
    if connection is None:
        _error(404, error_code="DB_NOT_FOUND", message=f"Database connection '{name}' not found")
        raise AssertionError("unreachable")

    metadata = get_metadata(name)
    if metadata is None:
        _error(404, error_code="METADATA_NOT_FOUND", message=f"Metadata for '{name}' not found")
        raise AssertionError("unreachable")

    return DatabaseDetailResponse(connection=connection, metadata=metadata)


@router.post("/{name}/refresh", response_model=SchemaMetadata)
def refresh_db(name: str = Path(pattern=r"^[a-zA-Z0-9-]+$")) -> SchemaMetadata:
    connection = get_connection_by_name(name)
    if connection is None:
        _error(404, error_code="DB_NOT_FOUND", message=f"Database connection '{name}' not found")
        raise AssertionError("unreachable")

    try:
        with connection_service.connect(connection.url) as conn:
            dialect = connection_service.detect_dialect(connection.url)
            metadata = metadata_service.fetch_metadata(name, conn, dialect)
        save_metadata(name, metadata)
    except Exception as exc:
        _error(
            500,
            error_code="METADATA_REFRESH_FAILED",
            message="Failed to refresh metadata",
            details=str(exc),
        )

    return metadata


@router.delete("/{name}", status_code=204)
def delete_db(name: str = Path(pattern=r"^[a-zA-Z0-9-]+$")) -> None:
    deleted = delete_connection(name)
    if not deleted:
        _error(404, error_code="DB_NOT_FOUND", message=f"Database connection '{name}' not found")
        raise AssertionError("unreachable")
