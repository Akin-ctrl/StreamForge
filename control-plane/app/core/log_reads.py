"""Helpers for reading recent gateway-runtime logs from persisted heartbeat state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Gateway
from app.schemas.logs import LogEntry


def _coerce_timestamp(value: object) -> datetime:
    """Parse one log timestamp into a timezone-aware datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        except ValueError:
            return datetime.fromtimestamp(0, tz=UTC)
    return datetime.fromtimestamp(0, tz=UTC)


def _component_name(entry: dict[str, object]) -> str:
    """Resolve the operator-facing component name for one log entry."""
    component = entry.get("component")
    if isinstance(component, str) and component.strip():
        return component

    logger_name = entry.get("logger")
    if isinstance(logger_name, str) and logger_name.strip():
        parts = [part for part in logger_name.split(".") if part]
        if parts[0] in {"gateway_runtime", "adapters", "sinks"} and len(parts) > 1:
            return parts[-1]
        return parts[0]

    return "runtime"


def collect_runtime_log_entries(
    gateways: Iterable[Gateway],
    *,
    component: str | None = None,
    level: str | None = None,
    limit: int = 200,
) -> list[LogEntry]:
    """Flatten recent runtime logs from one or more gateways into a sorted list."""
    if limit <= 0:
        return []

    component_filter = component.casefold() if component else None
    level_filter = level.upper() if level else None
    entries: list[LogEntry] = []

    for gateway in gateways:
        runtime_health = gateway.runtime_health if isinstance(gateway.runtime_health, dict) else {}
        recent_logs = runtime_health.get("recent_logs", [])
        if not isinstance(recent_logs, list):
            continue

        for raw_entry in recent_logs:
            if not isinstance(raw_entry, dict):
                continue

            entry_component = _component_name(raw_entry)
            entry_logger = raw_entry.get("logger")
            logger_name = entry_logger if isinstance(entry_logger, str) and entry_logger.strip() else "gateway_runtime"
            entry_level_raw = raw_entry.get("level")
            entry_level = entry_level_raw.upper() if isinstance(entry_level_raw, str) else "INFO"
            if component_filter and component_filter != entry_component.casefold():
                continue
            if level_filter and level_filter != entry_level:
                continue

            entries.append(
                LogEntry(
                    timestamp=_coerce_timestamp(raw_entry.get("timestamp")),
                    gateway_id=gateway.gateway_id,
                    level=entry_level,
                    logger=logger_name,
                    component=entry_component,
                    message=str(raw_entry.get("message", "")),
                    exception=str(raw_entry["exception"]) if raw_entry.get("exception") else None,
                )
            )

    entries.sort(key=lambda entry: entry.timestamp, reverse=True)
    return entries[:limit]


def list_runtime_log_entries(
    db: Session,
    *,
    gateway_id: str | None = None,
    component: str | None = None,
    level: str | None = None,
    limit: int = 200,
) -> list[LogEntry]:
    """Query gateway heartbeat state and return filtered recent runtime logs."""
    statement = select(Gateway).order_by(Gateway.gateway_id.asc())
    if gateway_id:
        statement = statement.where(Gateway.gateway_id == gateway_id)
    gateways = db.execute(statement).scalars().all()
    return collect_runtime_log_entries(
        gateways,
        component=component,
        level=level,
        limit=limit,
    )
