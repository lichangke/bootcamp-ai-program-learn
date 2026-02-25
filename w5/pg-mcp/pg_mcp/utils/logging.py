"""Structured logging helpers."""

import json
import logging
import sys
from datetime import UTC, datetime

from pg_mcp.request_context import get_request_id

_RESERVED_KEYS = set(logging.makeLogRecord({}).__dict__.keys())


class JsonFormatter(logging.Formatter):
    """Format log records as one-line JSON payloads."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = getattr(record, "request_id", None) or get_request_id()
        if request_id is not None:
            payload["request_id"] = request_id

        for key, value in record.__dict__.items():
            if key in _RESERVED_KEYS:
                continue
            if key in {"msg", "args", "levelname", "levelno", "name"}:
                continue
            payload[key] = value

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(log_level: str = "INFO") -> None:
    """Configure root logger to emit structured JSON logs to stderr."""
    level_name = (log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())

    root.handlers.clear()
    root.addHandler(handler)
