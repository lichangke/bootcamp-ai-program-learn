from app.core.config import Settings
from app.models.schemas.health import HealthResponse
from app.repositories.health_repository import HealthRepository


class HealthService:
    def __init__(self, repository: HealthRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def get_health(self) -> HealthResponse:
        database_health = self.repository.check_connection(self.settings.database_url)
        status = "ok" if database_health.connected else "degraded"
        return HealthResponse(
            status=status,
            environment=self.settings.app_env,
            database=database_health,
        )
