from __future__ import annotations

from urllib.parse import ParseResult

import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.services.connection_service import ConnectionService, ConnectionValidationError


class _FailingAdapter:
    schemes = ("mysql",)

    def validate_url(self, url: str) -> ParseResult:
        return ParseResult(
            scheme="mysql",
            netloc="root:password@localhost:3306",
            path="/interview_db",
            params="",
            query="",
            fragment="",
        )

    def connect(self, url: str, timeout: int) -> None:
        _ = url, timeout
        raise RuntimeError(
            "'cryptography' package is required for "
            "sha256_password or caching_sha2_password auth methods"
        )


class _FakeRegistry:
    def __init__(self, adapter: _FailingAdapter) -> None:
        self._adapter = adapter

    def resolve_by_url(self, _: str) -> _FailingAdapter:
        return self._adapter


def test_connection_service_wraps_mysql_auth_error() -> None:
    service = ConnectionService(_FakeRegistry(_FailingAdapter()))  # type: ignore[arg-type]
    with pytest.raises(ConnectionValidationError) as exc_info:
        service.connect("mysql://root:password@localhost:3306/interview_db")
    assert "Failed to connect to database" in str(exc_info.value)
    assert "cryptography" in str(exc_info.value)


def test_natural_query_maps_connection_error_to_400(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.api.v1.query as query_api

    def _raise_connection_error(*_: object, **__: object) -> None:
        raise ConnectionValidationError("Failed to connect to database: missing dependency")

    monkeypatch.setattr(
        query_api.orchestrator,
        "generate_sql_from_natural",
        _raise_connection_error,
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/dbs/interview_db/query/natural",
        json={"prompt": "top 5 users"},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["errorType"] == "connection"
    assert detail["errorCode"] == "CONNECTION_FAILED"
    assert "Failed to connect to database" in detail["message"]
