from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core import telemetry_reads


class _FakeCursor:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.executed: list[tuple[str, list | tuple | None]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def execute(self, sql: str, params: list | tuple | None = None) -> None:
        self.executed.append((sql, params))

    def fetchall(self) -> list[dict]:
        return list(self._rows)


class _FakeConnection:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._rows)


def test_list_event_records_returns_empty_when_event_table_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    source = telemetry_reads.TimescaleReadSource(
        sink_id="timescaledb-events",
        table="events",
        topic="events.clean",
        message_format="event",
        dsn="postgresql://example",
    )

    monkeypatch.setattr(telemetry_reads, "_timescaledb_sources", lambda db: [source])
    monkeypatch.setattr(telemetry_reads, "_table_exists", lambda source: False)

    records = telemetry_reads.list_event_records(object())

    assert records == []


def test_list_event_records_sorts_rows_from_multiple_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    first_source = telemetry_reads.TimescaleReadSource(
        sink_id="timescaledb-events-a",
        table="events_a",
        topic="events.clean",
        message_format="event",
        dsn="dsn-a",
    )
    second_source = telemetry_reads.TimescaleReadSource(
        sink_id="timescaledb-events-b",
        table="events_b",
        topic="events.clean",
        message_format="event",
        dsn="dsn-b",
    )
    rows_by_dsn = {
        "dsn-a": [
            {
                "id": 1,
                "asset_id": "asset-a",
                "event_type": "motor_start",
                "classification": "EVENT",
                "gateway_time": datetime(2026, 5, 19, 14, 0, tzinfo=timezone.utc),
                "device_time": None,
                "previous_state": {"motor_running": False},
                "new_state": {"motor_running": True},
                "metadata": {"source_topic": "events.clean"},
                "payload": {"gateway_id": "gw-1"},
            }
        ],
        "dsn-b": [
            {
                "id": 2,
                "asset_id": "asset-b",
                "event_type": "motor_stop",
                "classification": "EVENT",
                "gateway_time": datetime(2026, 5, 19, 14, 5, tzinfo=timezone.utc),
                "device_time": None,
                "previous_state": {"motor_running": True},
                "new_state": {"motor_running": False},
                "metadata": {"source_topic": "events.clean"},
                "payload": {"gateway_id": "gw-2"},
            }
        ],
    }

    monkeypatch.setattr(telemetry_reads, "_timescaledb_sources", lambda db: [first_source, second_source])
    monkeypatch.setattr(telemetry_reads, "_table_exists", lambda source: True)
    monkeypatch.setattr(
        telemetry_reads.psycopg,
        "connect",
        lambda dsn, connect_timeout, row_factory: _FakeConnection(rows_by_dsn[dsn]),
    )

    records = telemetry_reads.list_event_records(object())

    assert [record.record_id for record in records] == [2, 1]
    assert records[0].gateway_id == "gw-2"
    assert records[1].source_sink_id == "timescaledb-events-a"


def test_list_aggregate_records_uses_requested_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    source_1s = telemetry_reads.TimescaleReadSource(
        sink_id="timescaledb-aggregate-1s",
        table="telemetry_1s",
        topic="telemetry.1s",
        message_format="aggregate",
        dsn="dsn-1s",
    )
    source_1min = telemetry_reads.TimescaleReadSource(
        sink_id="timescaledb-aggregate-1min",
        table="telemetry_1min",
        topic="telemetry.1min",
        message_format="aggregate",
        dsn="dsn-1min",
    )
    aggregate_row = {
        "id": 11,
        "asset_id": "asset-a",
        "parameter": "temperature",
        "unit": "celsius",
        "classification": "TELEMETRY_AGGREGATE",
        "window_start": datetime(2026, 5, 19, 14, 0, tzinfo=timezone.utc),
        "window_end": datetime(2026, 5, 19, 14, 1, tzinfo=timezone.utc),
        "avg": 12.5,
        "min": 10.0,
        "max": 15.0,
        "stddev": 1.2,
        "count": 60,
        "p50": 12.0,
        "p95": 14.8,
        "p99": 15.0,
        "good_samples": 60,
        "suspect_samples": 0,
        "uncertain_samples": 0,
        "bad_samples": 0,
        "pct_good": 100.0,
        "payload": {"metadata": {"resolution": "1min"}},
    }

    monkeypatch.setattr(telemetry_reads, "_timescaledb_sources", lambda db: [source_1s, source_1min])
    monkeypatch.setattr(telemetry_reads, "_table_exists", lambda source: True)
    monkeypatch.setattr(
        telemetry_reads.psycopg,
        "connect",
        lambda dsn, connect_timeout, row_factory: _FakeConnection([aggregate_row] if dsn == "dsn-1min" else []),
    )

    records = telemetry_reads.list_aggregate_records(object(), resolution="1min")

    assert len(records) == 1
    assert records[0].resolution == "1min"
    assert records[0].source_sink_id == "timescaledb-aggregate-1min"
