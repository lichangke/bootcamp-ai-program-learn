"""Response models for MCP tool outputs."""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class QueryResultData(BaseModel):
    """Normalized query result payload."""

    columns: list[str]
    rows: list[list]
    row_count: int
    truncated: bool
    execution_time_ms: int


class ValidationInfo(BaseModel):
    """Validation metadata for generated SQL."""

    status: str = "passed"
    confidence: float | None = None
    message: str | None = None


class QueryMetadata(BaseModel):
    """Metadata for query execution."""

    database: str
    execution_time_ms: int | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class QueryResponseData(BaseModel):
    """Payload for successful query responses."""

    sql: str | None = None
    result: QueryResultData | None = None
    validation: ValidationInfo | None = None
    metadata: QueryMetadata | None = None


class QueryResponse(BaseModel):
    """Success response envelope."""

    success: bool = True
    data: QueryResponseData
    request_id: str = Field(default_factory=lambda: str(uuid4()))


class ErrorResponse(BaseModel):
    """Error response envelope with unified shape."""

    success: bool = False
    code: str
    message: str
    details: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def model_dump(self, *args, **kwargs) -> dict:
        """Serialize as {success, error:{code,message,details}, timestamp}."""
        _ = super().model_dump(*args, **kwargs)
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
            "timestamp": self.timestamp.isoformat(),
        }

