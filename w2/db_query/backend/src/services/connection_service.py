from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import ParseResult, parse_qs, unquote, urlparse

import psycopg2
import pymysql

from src.models.connection import DatabaseConnection
from src.services.dialect_service import (
    DatabaseDialect,
    DialectDetectionError,
    detect_dialect_from_parsed,
)


class ConnectionValidationError(ValueError):
    """Raised when a database connection URL is invalid or unreachable."""


class ConnectionService:
    def _resolve_dialect(self, parsed: ParseResult) -> DatabaseDialect:
        try:
            return detect_dialect_from_parsed(parsed)
        except DialectDetectionError as exc:
            raise ConnectionValidationError(str(exc)) from exc

    def validate_connection_url(self, url: str) -> tuple[ParseResult, DatabaseDialect]:
        parsed = urlparse(url)
        dialect = self._resolve_dialect(parsed)
        if not parsed.hostname:
            raise ConnectionValidationError("Database host is required")
        if not parsed.path or parsed.path == "/":
            raise ConnectionValidationError("Database name is required in URL path")
        return parsed, dialect

    def detect_dialect(self, url: str) -> DatabaseDialect:
        parsed = urlparse(url)
        return self._resolve_dialect(parsed)

    def _mysql_connect_kwargs(self, parsed: ParseResult, timeout: int) -> dict[str, Any]:
        params = parse_qs(parsed.query)
        database = parsed.path.lstrip("/")
        kwargs: dict[str, Any] = {
            "host": parsed.hostname,
            "user": unquote(parsed.username) if parsed.username else None,
            "password": unquote(parsed.password) if parsed.password else None,
            "database": database,
            "port": parsed.port or 3306,
            "connect_timeout": timeout,
            "charset": params.get("charset", ["utf8mb4"])[0],
            "autocommit": True,
        }
        return kwargs

    def _connect_with_dialect(self, url: str, dialect: DatabaseDialect, timeout: int) -> Any:
        if dialect == DatabaseDialect.POSTGRES:
            return psycopg2.connect(url, connect_timeout=timeout)
        parsed = urlparse(url)
        kwargs = self._mysql_connect_kwargs(parsed, timeout=timeout)
        return pymysql.connect(**kwargs)

    def test_connection(self, url: str) -> None:
        _, dialect = self.validate_connection_url(url)
        try:
            with (
                self._connect_with_dialect(url, dialect, timeout=5) as conn,
                conn.cursor() as cursor,
            ):
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
        _, dialect = self.validate_connection_url(url)
        return self._connect_with_dialect(url, dialect, timeout=10)
