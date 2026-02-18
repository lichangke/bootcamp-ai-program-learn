from app.core.db import ping_database
from app.models.schemas.health import DatabaseHealth


class HealthRepository:
    def check_connection(self, database_url: str) -> DatabaseHealth:
        connected, error_message = ping_database(database_url)
        return DatabaseHealth(
            connected=connected,
            message=None if connected else error_message,
        )
