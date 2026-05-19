"""Structured JSON logging helpers."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import logging
import sys
from threading import Lock
from typing import Any


_RECENT_LOG_CAPACITY = 500
_RECENT_LOGS: deque[dict[str, object]] = deque(maxlen=_RECENT_LOG_CAPACITY)
_RECENT_LOGS_LOCK = Lock()


def _default_component_name(logger_name: str) -> str:
    """Collapse logger names into an operator-readable component label."""
    parts = [part for part in logger_name.split(".") if part]
    if not parts:
        return "runtime"
    if parts[0] in {"gateway_runtime", "adapters", "sinks"} and len(parts) > 1:
        return parts[-1]
    return parts[0]


def _payload_for_record(record: logging.LogRecord) -> dict[str, object]:
    """Build one structured payload from a Python log record."""
    component = getattr(record, "component", None)
    if not isinstance(component, str) or not component.strip():
        component = _default_component_name(record.name)

    payload: dict[str, object] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "component": component,
        "message": record.getMessage(),
    }
    gateway_id = getattr(record, "gateway_id", None)
    if gateway_id:
        payload["gateway_id"] = gateway_id
    if record.exc_info:
        payload["exception"] = logging.Formatter().formatException(record.exc_info)
    return payload


class RecentLogBufferHandler(logging.Handler):
    """Keep a bounded in-memory tail of recent runtime log entries."""

    def emit(self, record: logging.LogRecord) -> None:
        payload = _payload_for_record(record)
        with _RECENT_LOGS_LOCK:
            _RECENT_LOGS.append(payload)


class JsonLogFormatter(logging.Formatter):
    """Format log records as compact JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = _payload_for_record(record)
        return json.dumps(payload, default=str)


def recent_log_entries(limit: int = 100, *, default_gateway_id: str | None = None) -> list[dict[str, object]]:
    """Return a copy of the most recent runtime log entries."""
    if limit <= 0:
        return []

    with _RECENT_LOGS_LOCK:
        entries = list(_RECENT_LOGS)[-limit:]

    copied_entries: list[dict[str, object]] = []
    for entry in entries:
        copied_entry = dict(entry)
        if default_gateway_id and not copied_entry.get("gateway_id"):
            copied_entry["gateway_id"] = default_gateway_id
        copied_entries.append(copied_entry)
    return copied_entries


def clear_recent_log_entries() -> None:
    """Clear the recent runtime log buffer."""
    with _RECENT_LOGS_LOCK:
        _RECENT_LOGS.clear()


def configure_json_logging(level: str = "INFO") -> None:
    """Replace root handlers with a structured stdout handler."""
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JsonLogFormatter())
    buffer_handler = RecentLogBufferHandler()
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(stdout_handler)
    root.addHandler(buffer_handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
