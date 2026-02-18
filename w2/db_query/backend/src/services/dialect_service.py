from __future__ import annotations

from enum import StrEnum
from urllib.parse import ParseResult, urlparse


class DatabaseDialect(StrEnum):
    POSTGRES = "postgres"
    MYSQL = "mysql"


class DialectDetectionError(ValueError):
    """Raised when database dialect cannot be inferred from URL."""


def detect_dialect_from_parsed(parsed: ParseResult) -> DatabaseDialect:
    scheme = parsed.scheme.lower()
    if scheme in {"postgres", "postgresql"}:
        return DatabaseDialect.POSTGRES
    if scheme in {"mysql"}:
        return DatabaseDialect.MYSQL
    raise DialectDetectionError(
        "Only PostgreSQL and MySQL URLs are supported",
    )


def detect_dialect_from_url(url: str) -> DatabaseDialect:
    parsed = urlparse(url)
    return detect_dialect_from_parsed(parsed)


def sqlglot_dialect_name(dialect: DatabaseDialect) -> str:
    if dialect == DatabaseDialect.MYSQL:
        return "mysql"
    return "postgres"
