"""Tests for request/response model layer."""


import pytest
from pydantic import ValidationError

from pg_mcp.models.request import QueryRequest
from pg_mcp.models.response import ErrorResponse, QueryResponse, QueryResponseData, QueryResultData


def test_query_request_valid_defaults() -> None:
    """QueryRequest should apply default return mode and limit."""
    request = QueryRequest(query="show users")
    assert request.return_mode == "both"
    assert request.limit == 100


@pytest.mark.parametrize("invalid_limit", [0, 1001])
def test_query_request_limit_validation(invalid_limit: int) -> None:
    """QueryRequest should reject out-of-range limit values."""
    with pytest.raises(ValidationError):
        QueryRequest(query="show users", limit=invalid_limit)


def test_query_request_return_mode_validation() -> None:
    """QueryRequest should reject invalid return_mode values."""
    with pytest.raises(ValidationError):
        QueryRequest(query="show users", return_mode="invalid")


def test_query_response_request_id_generated() -> None:
    """QueryResponse should generate a unique request_id."""
    payload = QueryResponseData(sql="SELECT 1")
    response_a = QueryResponse(data=payload)
    response_b = QueryResponse(data=payload)
    assert response_a.request_id
    assert response_a.request_id != response_b.request_id


def test_error_response_custom_dump_shape() -> None:
    """ErrorResponse model_dump should expose unified nested error structure."""
    response = ErrorResponse(
        code="DB_NOT_FOUND",
        message="missing db",
        details={"database": "analytics"},
        request_id="req-1",
    )
    dumped = response.model_dump()
    assert dumped["success"] is False
    assert dumped["error"]["code"] == "DB_NOT_FOUND"
    assert dumped["error"]["details"]["database"] == "analytics"
    assert dumped["request_id"] == "req-1"
    assert "timestamp" in dumped


def test_query_result_data_shape() -> None:
    """QueryResultData should preserve row_count to rows size contract."""
    result = QueryResultData(
        columns=["id"],
        rows=[[1], [2]],
        row_count=2,
        truncated=False,
        execution_time_ms=5,
    )
    assert result.row_count == len(result.rows)
