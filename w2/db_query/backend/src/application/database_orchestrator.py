from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from src.infrastructure.registry import AdapterRegistry
from src.models.connection import DatabaseConnection, SupportedDialect
from src.models.metadata import SchemaMetadata, TableMetadata
from src.models.query import NaturalLanguageContext, NaturalQueryResponse, QueryResult
from src.services.connection_service import ConnectionService
from src.services.llm_service import LlmService
from src.services.query_service import QueryService, QueryValidationError
from src.storage.sqlite_store import (
    delete_connection,
    get_connection_by_name,
    get_metadata,
    list_connections,
    save_metadata,
    upsert_connection,
)


class DatabaseNotFoundError(LookupError):
    """Raised when a named database connection cannot be found."""


class MetadataNotFoundError(LookupError):
    """Raised when metadata does not exist for a named connection."""


class DatabaseOrchestrator:
    def __init__(
        self,
        *,
        registry: AdapterRegistry,
        connection_service: ConnectionService,
        query_service: QueryService,
        llm_service: LlmService,
    ) -> None:
        self._registry = registry
        self._connection_service = connection_service
        self._query_service = query_service
        self._llm_service = llm_service

    def list_connections(self) -> list[DatabaseConnection]:
        return list_connections()

    def upsert_connection_and_metadata(self, *, name: str, url: str) -> DatabaseConnection:
        adapter = self._connection_service.test_connection(url)
        existing = get_connection_by_name(name)
        dialect = cast(SupportedDialect, adapter.name)
        model = self._connection_service.create_connection_model(
            name=name,
            url=url,
            dialect=dialect,
            existing=existing,
        )
        upsert_connection(model)

        connected_adapter, conn = self._connection_service.connect(model.url)
        try:
            metadata = connected_adapter.fetch_metadata(name, conn)
        finally:
            conn.close()

        save_metadata(name, metadata)
        return model

    def get_database_detail(self, name: str) -> tuple[DatabaseConnection, SchemaMetadata]:
        connection = get_connection_by_name(name)
        if connection is None:
            raise DatabaseNotFoundError(f"Database connection '{name}' not found")

        metadata = get_metadata(name)
        if metadata is None:
            raise MetadataNotFoundError(f"Metadata for '{name}' not found")

        return connection, metadata

    def refresh_metadata(self, name: str) -> SchemaMetadata:
        connection = get_connection_by_name(name)
        if connection is None:
            raise DatabaseNotFoundError(f"Database connection '{name}' not found")

        connected_adapter, conn = self._connection_service.connect(connection.url)
        try:
            metadata = connected_adapter.fetch_metadata(name, conn)
        finally:
            conn.close()

        save_metadata(name, metadata)
        return metadata

    def delete_connection(self, name: str) -> None:
        if not delete_connection(name):
            raise DatabaseNotFoundError(f"Database connection '{name}' not found")

    def execute_sql(self, *, name: str, sql: str) -> QueryResult:
        connection = get_connection_by_name(name)
        if connection is None:
            raise DatabaseNotFoundError(f"Database connection '{name}' not found")

        adapter = self._registry.resolve_by_url(connection.url)
        validated_sql = self._query_service.validate_sql(sql, adapter.sqlglot_dialect)

        connected_adapter, conn = self._connection_service.connect(connection.url)
        try:
            return self._query_service.execute_query(conn, validated_sql, connected_adapter)
        finally:
            conn.close()

    def generate_sql_from_natural(self, *, name: str, prompt: str) -> NaturalQueryResponse:
        connection = get_connection_by_name(name)
        if connection is None:
            raise DatabaseNotFoundError(f"Database connection '{name}' not found")

        metadata = get_metadata(name)
        if metadata is None:
            raise MetadataNotFoundError(f"Metadata for '{name}' not found")

        adapter = self._registry.resolve_by_url(connection.url)
        limited_tables, schema_context, prompt_schema = self._llm_service.prepare_schema_context(
            metadata,
            prompt,
        )
        generated_sql = self._llm_service.generate_sql(
            prompt=prompt,
            connection_name=name,
            schema_prompt_context=prompt_schema,
            dialect_label=adapter.llm_dialect_label(),
            sqlglot_dialect=adapter.sqlglot_dialect,
        )
        validated_sql = self._query_service.validate_sql(generated_sql, adapter.sqlglot_dialect)
        executable_sql = self._ensure_executable_natural_sql(
            connection_url=connection.url,
            prompt=prompt,
            prompt_schema=prompt_schema,
            sql=validated_sql,
            sqlglot_dialect=adapter.sqlglot_dialect,
            dialect_label=adapter.llm_dialect_label(),
        )

        typed_context: dict[str, TableMetadata] = schema_context
        context = NaturalLanguageContext(
            connection_name=name,
            user_prompt=prompt,
            relevant_tables=limited_tables,
            schema_context=typed_context,
            generated_sql=executable_sql,
            timestamp=datetime.now(UTC),
        )
        return NaturalQueryResponse(generated_sql=executable_sql, context=context)

    def get_connection(self, name: str) -> DatabaseConnection:
        connection = get_connection_by_name(name)
        if connection is None:
            raise DatabaseNotFoundError(f"Database connection '{name}' not found")
        return connection

    def _ensure_executable_natural_sql(
        self,
        *,
        connection_url: str,
        prompt: str,
        prompt_schema: dict[str, object],
        sql: str,
        sqlglot_dialect: str,
        dialect_label: str,
    ) -> str:
        _, conn = self._connection_service.connect(connection_url)
        try:
            self._query_service.probe_query(conn, sql)
            return sql
        except Exception as primary_exc:
            fallback_sql = self._llm_service.build_fallback_sql(
                prompt=prompt,
                schema_prompt_context=prompt_schema,
                sqlglot_dialect=sqlglot_dialect,
            )
            validated_fallback = self._query_service.validate_sql(fallback_sql, sqlglot_dialect)
            if validated_fallback.strip() == sql.strip():
                raise QueryValidationError(
                    f"Generated SQL is not executable for {dialect_label}: {primary_exc}"
                ) from primary_exc
            try:
                self._query_service.probe_query(conn, validated_fallback)
                return validated_fallback
            except Exception as fallback_exc:
                raise QueryValidationError(
                    "Generated SQL is not executable and fallback SQL also failed. "
                    f"{dialect_label} errors: primary={primary_exc}; fallback={fallback_exc}"
                ) from fallback_exc
        finally:
            conn.close()
