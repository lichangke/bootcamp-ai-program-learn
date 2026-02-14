from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import ParseResult, urlparse

import psycopg2

from src.models.connection import DatabaseConnection


class ConnectionValidationError(ValueError):
    """Raised when a PostgreSQL connection URL is invalid or unreachable."""


class ConnectionService:
    def validate_connection_url(self, url: str) -> ParseResult:
        parsed = urlparse(url)
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise ConnectionValidationError("Only PostgreSQL URLs are supported")
        if not parsed.hostname:
            raise ConnectionValidationError("Database host is required")
        if not parsed.path or parsed.path == "/":
            raise ConnectionValidationError("Database name is required in URL path")
        return parsed

    def test_connection(self, url: str) -> None:
        self.validate_connection_url(url)
        try:
            with psycopg2.connect(url, connect_timeout=5) as conn, conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as exc:
            raise ConnectionValidationError(f"Failed to connect to database: {exc}") from exc

    def create_connection_model(
        self,
        name: str,
        url: str,
        existing: DatabaseConnection | None = None,
    ) -> DatabaseConnection:
        now = datetime.now(UTC)
        created_at = existing.created_at if existing else now
        return DatabaseConnection(
            name=name,
            url=url,
            created_at=created_at,
            updated_at=now,
            status="active",
        )

    def connect(self, url: str) -> Any:
        self.validate_connection_url(url)
        return psycopg2.connect(url, connect_timeout=10)
