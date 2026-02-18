from __future__ import annotations

from typing import Any, Protocol
from urllib.parse import ParseResult

from src.models.metadata import SchemaMetadata


class DbAdapter(Protocol):
    name: str
    schemes: tuple[str, ...]
    sqlglot_dialect: str

    def parse_url(self, url: str) -> ParseResult:
        """Parse connection URL."""

    def validate_url(self, url: str) -> ParseResult:
        """Validate URL format and required parts."""

    def connect(self, url: str, timeout: int) -> Any:
        """Open a DBAPI compatible connection."""

    def test_connection(self, url: str) -> None:
        """Run lightweight connectivity check."""

    def fetch_metadata(self, connection_name: str, conn: Any) -> SchemaMetadata:
        """Fetch schema metadata snapshot."""

    def normalize_column_name(self, column: Any) -> str:
        """Extract column name from DBAPI description row."""

    def normalize_column_type(self, column: Any) -> str:
        """Extract column type from DBAPI description row."""

    def llm_dialect_label(self) -> str:
        """Human-readable dialect label for prompting."""
