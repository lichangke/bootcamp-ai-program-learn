from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    connected: bool
    message: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str = "project-alpha-backend"
    environment: str
    database: DatabaseHealth
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
