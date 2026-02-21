from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import ParseResult

from src.domain.interfaces.db_adapter import DbAdapter
from src.infrastructure.registry import AdapterRegistry
from src.models.connection import DatabaseConnection, SupportedDialect


class ConnectionValidationError(ValueError):
    """Raised when a database connection URL is invalid or unreachable."""


class ConnectionService:
    def __init__(self, registry: AdapterRegistry) -> None:
        self._registry = registry

    def resolve_adapter(self, url: str) -> DbAdapter:
        try:
            return self._registry.resolve_by_url(url)
        except ValueError as exc:
            raise ConnectionValidationError(str(exc)) from exc

    def validate_connection_url(self, url: str) -> tuple[ParseResult, DbAdapter]:
        adapter = self.resolve_adapter(url)
        try:
            parsed = adapter.validate_url(url)
        except Exception as exc:
            raise ConnectionValidationError(str(exc)) from exc
        return parsed, adapter

    def test_connection(self, url: str) -> DbAdapter:
        _, adapter = self.validate_connection_url(url)
        try:
            adapter.test_connection(url)
        except Exception as exc:
            raise ConnectionValidationError(f"Failed to connect to database: {exc}") from exc
        return adapter

    def create_connection_model(
        self,
        name: str,
        url: str,
        dialect: SupportedDialect,
        existing: DatabaseConnection | None = None,
    ) -> DatabaseConnection:
        now = datetime.now(UTC)
        created_at = existing.created_at if existing else now
        return DatabaseConnection(
            name=name,
            url=url,
            dialect=dialect,
            created_at=created_at,
            updated_at=now,
            status="active",
        )

    def connect(self, url: str, timeout: int = 10) -> tuple[DbAdapter, Any]:
        _, adapter = self.validate_connection_url(url)
        try:
            conn = adapter.connect(url, timeout=timeout)
        except Exception as exc:
            raise ConnectionValidationError(f"Failed to connect to database: {exc}") from exc
        return adapter, conn
