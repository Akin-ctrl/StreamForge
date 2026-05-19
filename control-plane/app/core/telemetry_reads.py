"""Timescale-backed read helpers for operator event and aggregate views."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secrets import list_resolved_secret_values
from app.db.models import Sink
from app.schemas.telemetry import AggregateItem, AggregateResolution, EventItem


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class TimescaleReadSource:
    """One operator-readable TimescaleDB sink target."""

    sink_id: str
    table: str
    topic: str
    message_format: str
    dsn: str


def list_event_records(
    db: Session,
    *,
    gateway_id: str | None = None,
    asset_id: str | None = None,
    event_type: str | None = None,
    classification: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 200,
) -> list[EventItem]:
    """Return cleaned event records from configured TimescaleDB sinks."""
    rows: list[EventItem] = []
    for source in _event_sources(db):
        rows.extend(
            _query_events_from_source(
                source,
                gateway_id=gateway_id,
                asset_id=asset_id,
                event_type=event_type,
                classification=classification,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )
        )

    rows.sort(key=lambda item: item.gateway_time, reverse=True)
    return rows[:limit]


def list_aggregate_records(
    db: Session,
    *,
    resolution: AggregateResolution,
    gateway_id: str | None = None,
    asset_id: str | None = None,
    parameter: str | None = None,
    classification: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 200,
) -> list[AggregateItem]:
    """Return aggregate records for one resolution from configured TimescaleDB sinks."""
    rows: list[AggregateItem] = []
    for source in _aggregate_sources(db, resolution):
        rows.extend(
            _query_aggregates_from_source(
                source,
                resolution=resolution,
                gateway_id=gateway_id,
                asset_id=asset_id,
                parameter=parameter,
                classification=classification,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )
        )

    rows.sort(key=lambda item: item.window_end, reverse=True)
    return rows[:limit]


def _event_sources(db: Session) -> list[TimescaleReadSource]:
    return [
        source
        for source in _timescaledb_sources(db)
        if source.message_format == "event" or source.topic.startswith("events.")
    ]


def _aggregate_sources(db: Session, resolution: AggregateResolution) -> list[TimescaleReadSource]:
    matching: list[TimescaleReadSource] = []
    for source in _timescaledb_sources(db):
        source_resolution = _resolution_for_source(source)
        if source_resolution == resolution:
            matching.append(source)
    return matching


def _timescaledb_sources(db: Session) -> list[TimescaleReadSource]:
    rows = db.execute(
        select(Sink)
        .where(Sink.sink_type == "timescaledb")
        .where(Sink.status == "active")
        .order_by(Sink.created_at.asc())
    ).scalars().all()
    resolved_secrets = list_resolved_secret_values(db, "sink", [row.sink_id for row in rows])

    sources: list[TimescaleReadSource] = []
    for row in rows:
        config = dict(row.config) if isinstance(row.config, dict) else {}
        table = str(config.get("table") or "").strip()
        topic = str(config.get("topic") or "").strip()
        dsn = str(resolved_secrets.get(row.sink_id, {}).get("db_dsn") or "").strip()
        if not table or not topic or not dsn:
            continue
        if not _IDENTIFIER_RE.fullmatch(table):
            continue
        sources.append(
            TimescaleReadSource(
                sink_id=row.sink_id,
                table=table,
                topic=topic,
                message_format=str(config.get("message_format") or "auto").strip().lower(),
                dsn=dsn,
            )
        )
    return sources


def _resolution_for_source(source: TimescaleReadSource) -> AggregateResolution | None:
    if source.topic == "telemetry.1s" or source.table.endswith("_1s"):
        return "1s"
    if source.topic == "telemetry.1min" or source.table.endswith("_1min"):
        return "1min"
    return None


def _query_events_from_source(
    source: TimescaleReadSource,
    *,
    gateway_id: str | None,
    asset_id: str | None,
    event_type: str | None,
    classification: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
    limit: int,
) -> list[EventItem]:
    if not _table_exists(source):
        return []

    sql = (
        "SELECT id, asset_id, event_type, classification, gateway_time, device_time, "
        "previous_state, new_state, metadata, payload "
        f'FROM "{source.table}"'
    )
    filters: list[str] = []
    params: list[Any] = []
    if gateway_id:
        filters.append("COALESCE(payload->>'gateway_id', '') = %s")
        params.append(gateway_id)
    if asset_id:
        filters.append("asset_id = %s")
        params.append(asset_id)
    if event_type:
        filters.append("event_type = %s")
        params.append(event_type)
    if classification:
        filters.append("classification = %s")
        params.append(classification)
    if start_time is not None:
        filters.append("gateway_time >= %s")
        params.append(start_time)
    if end_time is not None:
        filters.append("gateway_time <= %s")
        params.append(end_time)

    if filters:
        sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY gateway_time DESC LIMIT %s"
    params.append(limit)

    try:
        with psycopg.connect(source.dsn, connect_timeout=3, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                records = cursor.fetchall()
    except psycopg.Error as exc:
        raise HTTPException(status_code=502, detail=f"Failed to read event records from sink {source.sink_id}: {exc}") from exc

    items: list[EventItem] = []
    for record in records:
        payload = _json_dict(record.get("payload"))
        items.append(
            EventItem(
                source_sink_id=source.sink_id,
                source_table=source.table,
                record_id=int(record["id"]),
                gateway_id=_payload_gateway_id(payload),
                asset_id=str(record["asset_id"]),
                event_type=str(record["event_type"]),
                classification=str(record["classification"]),
                gateway_time=record["gateway_time"],
                device_time=record.get("device_time"),
                previous_state=_json_dict(record.get("previous_state")),
                new_state=_json_dict(record.get("new_state")),
                metadata=_json_dict(record.get("metadata")),
                payload=payload,
            )
        )
    return items


def _query_aggregates_from_source(
    source: TimescaleReadSource,
    *,
    resolution: AggregateResolution,
    gateway_id: str | None,
    asset_id: str | None,
    parameter: str | None,
    classification: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
    limit: int,
) -> list[AggregateItem]:
    if not _table_exists(source):
        return []

    sql = (
        "SELECT id, asset_id, parameter, unit, classification, window_start, window_end, "
        "avg, min, max, stddev, count, p50, p95, p99, good_samples, suspect_samples, "
        "uncertain_samples, bad_samples, pct_good, payload "
        f'FROM "{source.table}"'
    )
    filters: list[str] = []
    params: list[Any] = []
    if gateway_id:
        filters.append("COALESCE(payload->>'gateway_id', '') = %s")
        params.append(gateway_id)
    if asset_id:
        filters.append("asset_id = %s")
        params.append(asset_id)
    if parameter:
        filters.append("parameter = %s")
        params.append(parameter)
    if classification:
        filters.append("classification = %s")
        params.append(classification)
    if start_time is not None:
        filters.append("window_end >= %s")
        params.append(start_time)
    if end_time is not None:
        filters.append("window_end <= %s")
        params.append(end_time)

    if filters:
        sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY window_end DESC LIMIT %s"
    params.append(limit)

    try:
        with psycopg.connect(source.dsn, connect_timeout=3, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                records = cursor.fetchall()
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to read aggregate records from sink {source.sink_id}: {exc}",
        ) from exc

    items: list[AggregateItem] = []
    for record in records:
        payload = _json_dict(record.get("payload"))
        items.append(
            AggregateItem(
                resolution=resolution,
                source_sink_id=source.sink_id,
                source_table=source.table,
                record_id=int(record["id"]),
                gateway_id=_payload_gateway_id(payload),
                asset_id=str(record["asset_id"]),
                parameter=str(record["parameter"]),
                unit=_optional_text(record.get("unit")),
                classification=str(record["classification"]),
                window_start=record["window_start"],
                window_end=record["window_end"],
                avg=float(record["avg"]),
                min=float(record["min"]),
                max=float(record["max"]),
                stddev=float(record["stddev"]),
                count=int(record["count"]),
                p50=float(record["p50"]),
                p95=float(record["p95"]),
                p99=float(record["p99"]),
                good_samples=int(record["good_samples"]),
                suspect_samples=int(record["suspect_samples"]),
                uncertain_samples=int(record["uncertain_samples"]),
                bad_samples=int(record["bad_samples"]),
                pct_good=float(record["pct_good"]),
                payload=payload,
            )
        )
    return items


def _table_exists(source: TimescaleReadSource) -> bool:
    try:
        with psycopg.connect(source.dsn, connect_timeout=3, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT to_regclass(%s) AS table_name", (f"public.{source.table}",))
                row = cursor.fetchone()
    except psycopg.Error as exc:
        raise HTTPException(status_code=502, detail=f"Failed to inspect sink {source.sink_id}: {exc}") from exc
    return bool(row and row.get("table_name"))


def _json_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _optional_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _payload_gateway_id(payload: dict[str, Any]) -> str | None:
    raw_gateway_id = payload.get("gateway_id")
    if isinstance(raw_gateway_id, str) and raw_gateway_id.strip():
        return raw_gateway_id
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        metadata_gateway_id = metadata.get("gateway_id")
        if isinstance(metadata_gateway_id, str) and metadata_gateway_id.strip():
            return metadata_gateway_id
    return None
