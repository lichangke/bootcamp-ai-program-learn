from typing import Literal

from pydantic import Field

from src.models import CamelCaseModel


class QueryError(CamelCaseModel):
    error_type: Literal["connection", "syntax", "validation", "execution", "timeout"] = Field(
        description="Error category",
    )
    error_code: str = Field(description="Machine-readable code")
    message: str = Field(description="Human-readable message")
    details: str | None = Field(default=None, description="Technical details")
    query: str | None = Field(default=None, description="Related SQL query")

