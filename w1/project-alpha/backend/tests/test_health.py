from datetime import UTC, datetime

from app.api.routes.health import get_health_service
from app.main import app
from app.models.schemas.health import DatabaseHealth, HealthResponse
from fastapi.testclient import TestClient


class _HealthyService:
    def get_health(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            environment="test",
            database=DatabaseHealth(connected=True, message=None),
            timestamp=datetime.now(UTC),
        )


class _DegradedService:
    def get_health(self) -> HealthResponse:
        return HealthResponse(
            status="degraded",
            environment="test",
            database=DatabaseHealth(
                connected=False,
                message="connection timeout",
            ),
            timestamp=datetime.now(UTC),
        )


def test_health_ok(client: TestClient) -> None:
    app.dependency_overrides[get_health_service] = _HealthyService
    response = client.get("/api/health")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"]["connected"] is True


def test_health_degraded(client: TestClient) -> None:
    app.dependency_overrides[get_health_service] = _DegradedService
    response = client.get("/api/health")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["database"]["connected"] is False
