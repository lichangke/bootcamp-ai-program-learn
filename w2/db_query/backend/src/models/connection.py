from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from src.models import CamelCaseModel


class DatabaseConnection(CamelCaseModel):
    name: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9-]+$")
    url: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    status: Literal["active", "error", "unknown"] = "unknown"

    @field_validator("url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith(("postgres://", "postgresql://", "mysql://")):
            raise ValueError("URL must be a PostgreSQL or MySQL connection string")
        return value
