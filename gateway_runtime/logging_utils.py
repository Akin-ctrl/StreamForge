"""Structured JSON logging helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import sys


class JsonLogFormatter(logging.Formatter):
    """Format log records as compact JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        gateway_id = getattr(record, "gateway_id", None)
        component = getattr(record, "component", None)
        if gateway_id:
            payload["gateway_id"] = gateway_id
        if component:
            payload["component"] = component
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_json_logging(level: str = "INFO") -> None:
    """Replace root handlers with a structured stdout handler."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
