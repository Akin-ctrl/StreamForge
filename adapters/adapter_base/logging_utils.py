"""Structured JSON logging helpers for adapter containers."""

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
        adapter_id = getattr(record, "adapter_id", None)
        component = getattr(record, "component", None)
        if adapter_id:
            payload["adapter_id"] = adapter_id
        if component:
            payload["component"] = component
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_json_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
