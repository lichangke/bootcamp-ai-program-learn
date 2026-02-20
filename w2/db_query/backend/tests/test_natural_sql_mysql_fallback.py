from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
import src.application.database_orchestrator as orchestrator_module
from src.application.database_orchestrator import DatabaseOrchestrator
from src.models.connection import DatabaseConnection
from src.models.metadata import ColumnMetadata, SchemaMetadata, TableMetadata
from src.services.query_service import QueryValidationError


class _FakeAdapter:
    sqlglot_dialect = "mysql"

    def llm_dialect_label(self) -> str:
        return "MySQL"


class _FakeRegistry:
    def __init__(self, adapter: _FakeAdapter) -> None:
        self._adapter = adapter

    def resolve_by_url(self, _: str) -> _FakeAdapter:
        return self._adapter


class _FakeConn:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeConnectionService:
    def __init__(self, adapter: _FakeAdapter) -> None:
        self._adapter = adapter
        self.last_conn: _FakeConn | None = None

    def connect(self, _: str, timeout: int = 10) -> tuple[_FakeAdapter, _FakeConn]:
        _ = timeout
        conn = _FakeConn()
        self.last_conn = conn
        return self._adapter, conn


class _FakeQueryService:
    def __init__(self, *, fail_on: set[str]) -> None:
        self.fail_on = fail_on
        self.probed_sql: list[str] = []

    def validate_sql(self, sql: str, _: str) -> str:
        return sql

    def probe_query(self, conn: _FakeConn, sql: str) -> None:
        _ = conn
        self.probed_sql.append(sql)
        if any(fragment in sql for fragment in self.fail_on):
            raise RuntimeError(f"invalid sql: {sql}")


class _FakeLlmService:
    def __init__(self, generated_sql: str, fallback_sql: str) -> None:
        self._generated_sql = generated_sql
        self._fallback_sql = fallback_sql

    def prepare_schema_context(
        self,
        metadata: SchemaMetadata,
        prompt: str,
    ) -> tuple[list[str], dict[str, TableMetadata], dict[str, Any]]:
        _ = prompt
        first_table = metadata.tables[0]
        key = f"{first_table.schema_name}.{first_table.table_name}"
        return [key], {key: first_table}, {key: {"columns": [{"name": "id"}]}}

    def generate_sql(
        self,
        *,
        prompt: str,
        connection_name: str,
        schema_prompt_context: dict[str, Any],
        dialect_label: str = "PostgreSQL",
        sqlglot_dialect: str = "postgres",
    ) -> str:
        _ = prompt, connection_name, schema_prompt_context, dialect_label, sqlglot_dialect
        return self._generated_sql

    def build_fallback_sql(
        self,
        *,
        prompt: str,
        schema_prompt_context: dict[str, Any],
        sqlglot_dialect: str,
    ) -> str:
        _ = prompt, schema_prompt_context, sqlglot_dialect
        return self._fallback_sql


def _build_metadata() -> SchemaMetadata:
    return SchemaMetadata(
        connection_name="demo_mysql",
        database_name="interview_db",
        fetched_at=datetime.now(UTC),
        tables=[
            TableMetadata(
                schema_name="interview_db",
                table_name="applications",
                table_type="TABLE",
                columns=[
                    ColumnMetadata(
                        column_name="id",
                        data_type="int",
                        is_nullable=False,
                    )
                ],
                primary_keys=["id"],
            )
        ],
        views=[],
    )


def _build_connection() -> DatabaseConnection:
    now = datetime.now(UTC)
    return DatabaseConnection(
        name="demo_mysql",
        url="mysql://root:password@localhost:3306/interview_db",
        dialect="mysql",
        created_at=now,
        updated_at=now,
        status="active",
    )


def test_generate_sql_from_natural_falls_back_when_primary_is_not_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = _build_metadata()
    connection = _build_connection()
    generated_sql = (
        "SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY expected_salary) "
        "FROM interview_db.applications"
    )
    fallback_sql = "SELECT * FROM interview_db.applications LIMIT 1000"

    adapter = _FakeAdapter()
    query_service = _FakeQueryService(fail_on={"PERCENTILE_CONT"})
    connection_service = _FakeConnectionService(adapter)
    llm_service = _FakeLlmService(generated_sql=generated_sql, fallback_sql=fallback_sql)

    monkeypatch.setattr(orchestrator_module, "get_connection_by_name", lambda _: connection)
    monkeypatch.setattr(orchestrator_module, "get_metadata", lambda _: metadata)

    orchestrator = DatabaseOrchestrator(
        registry=_FakeRegistry(adapter),
        connection_service=connection_service,
        query_service=query_service,  # type: ignore[arg-type]
        llm_service=llm_service,  # type: ignore[arg-type]
    )

    result = orchestrator.generate_sql_from_natural(
        name="demo_mysql",
        prompt="95 percentile salary",
    )

    assert result.generated_sql == fallback_sql
    assert query_service.probed_sql == [generated_sql, fallback_sql]
    assert connection_service.last_conn is not None
    assert connection_service.last_conn.closed


def test_generate_sql_from_natural_raises_when_primary_and_fallback_both_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = _build_metadata()
    connection = _build_connection()
    generated_sql = "SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY expected_salary) FROM t"
    fallback_sql = "SELECT * FROM interview_db.applications LIMIT 1000"

    adapter = _FakeAdapter()
    query_service = _FakeQueryService(fail_on={"PERCENTILE_CONT", "SELECT *"})
    connection_service = _FakeConnectionService(adapter)
    llm_service = _FakeLlmService(generated_sql=generated_sql, fallback_sql=fallback_sql)

    monkeypatch.setattr(orchestrator_module, "get_connection_by_name", lambda _: connection)
    monkeypatch.setattr(orchestrator_module, "get_metadata", lambda _: metadata)

    orchestrator = DatabaseOrchestrator(
        registry=_FakeRegistry(adapter),
        connection_service=connection_service,
        query_service=query_service,  # type: ignore[arg-type]
        llm_service=llm_service,  # type: ignore[arg-type]
    )

    with pytest.raises(QueryValidationError):
        orchestrator.generate_sql_from_natural(name="demo_mysql", prompt="95 percentile salary")
