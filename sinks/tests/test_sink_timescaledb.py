"""Tests for TimescaleDB sink health and circuit breaker reporting."""

from __future__ import annotations

import sys
import types
import unittest

from gateway_runtime.circuit_breaker import CircuitBreaker


class _FakeFastAPI:
    def __init__(self, *args, **kwargs) -> None:
        return None

    def get(self, _path: str):
        def decorator(func):
            return func

        return decorator


sys.modules.setdefault("fastapi", types.SimpleNamespace(FastAPI=_FakeFastAPI))
sys.modules.setdefault("uvicorn", types.SimpleNamespace(run=lambda *args, **kwargs: None))

from sinks.sink_timescaledb import main as sink_main


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class SinkTimescaleHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_breaker = sink_main._DB_BREAKER
        self.original_stats = dict(sink_main._STATS)

    def tearDown(self) -> None:
        sink_main._DB_BREAKER = self.original_breaker
        sink_main._STATS.clear()
        sink_main._STATS.update(self.original_stats)

    def test_health_is_failed_when_breaker_is_open(self) -> None:
        clock = FakeClock()
        sink_main._DB_BREAKER = CircuitBreaker("timescaledb_sink", failure_threshold=2, open_duration_seconds=30, clock=clock.now)
        sink_main._DB_BREAKER.record_failure(RuntimeError("db down"))
        sink_main._DB_BREAKER.record_failure(RuntimeError("db down"))

        payload = sink_main._health_payload()

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["circuit_breaker"]["state"], "open")

    def test_health_is_degraded_when_last_error_exists(self) -> None:
        clock = FakeClock()
        sink_main._DB_BREAKER = CircuitBreaker("timescaledb_sink", failure_threshold=5, open_duration_seconds=30, clock=clock.now)
        sink_main._STATS["last_error"] = "temporary timeout"

        payload = sink_main._health_payload()

        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["circuit_breaker"]["state"], "closed")

    def test_payload_format_detects_aggregate_messages(self) -> None:
        aggregate_payload = {
            "asset_id": "line-01",
            "parameter": "temperature",
            "window_start": "2026-05-14T10:00:00Z",
            "window_end": "2026-05-14T10:01:00Z",
            "aggregates": {"avg": 88.0},
        }

        self.assertEqual(sink_main._payload_format(aggregate_payload, "auto"), "aggregate")
        self.assertEqual(sink_main._payload_format(aggregate_payload, "telemetry"), "telemetry")

    def test_payload_format_detects_event_messages(self) -> None:
        event_payload = {
            "asset_id": "line-01",
            "event_type": "motor_state_change",
            "classification": "EVENT",
            "previous_state": {"motor_running": False},
            "new_state": {"motor_running": True},
            "timestamps": {"gateway_time": "2026-05-14T10:00:00Z", "device_time": None},
            "metadata": {"adapter_id": "adapter-1", "pipeline_id": "line-01"},
        }

        self.assertEqual(sink_main._payload_format(event_payload, "auto"), "event")
        self.assertEqual(sink_main._payload_format(event_payload, "event"), "event")

    def test_write_payload_inserts_aggregate_row_shape(self) -> None:
        calls: list[tuple[str, tuple]] = []

        class FakeCursor:
            def execute(self, query: str, params: tuple) -> None:
                calls.append((query, params))

        payload = {
            "asset_id": "line-01",
            "parameter": "temperature",
            "unit": "celsius",
            "classification": "TELEMETRY_AGGREGATE",
            "window_start": "2026-05-14T10:00:00Z",
            "window_end": "2026-05-14T10:00:01Z",
            "aggregates": {
                "avg": 88.0,
                "min": 87.5,
                "max": 88.5,
                "stddev": 0.4,
                "count": 3,
                "p50": 88.0,
                "p95": 88.45,
                "p99": 88.49,
            },
            "quality_summary": {
                "good_samples": 3,
                "suspect_samples": 0,
                "uncertain_samples": 0,
                "bad_samples": 0,
                "pct_good": 100.0,
            },
        }

        written = sink_main._write_payload(FakeCursor(), "telemetry_1s", payload, "aggregate")

        self.assertEqual(written, 1)
        self.assertEqual(len(calls), 1)
        self.assertIn("window_start", calls[0][0])
        self.assertIn("ON CONFLICT", calls[0][0])
        self.assertEqual(calls[0][1][0], "line-01")
        self.assertEqual(calls[0][1][6], 88.0)

    def test_write_payload_inserts_event_row_shape(self) -> None:
        calls: list[tuple[str, tuple]] = []

        class FakeCursor:
            def execute(self, query: str, params: tuple) -> None:
                calls.append((query, params))

        payload = {
            "asset_id": "line-01",
            "event_type": "motor_state_change",
            "classification": "EVENT",
            "previous_state": {"motor_running": False},
            "new_state": {"motor_running": True},
            "timestamps": {
                "gateway_time": "2026-05-14T10:00:00Z",
                "device_time": None,
            },
            "metadata": {
                "adapter_id": "adapter-1",
                "pipeline_id": "line-01",
            },
        }

        written = sink_main._write_payload(FakeCursor(), "events", payload, "event")

        self.assertEqual(written, 1)
        self.assertEqual(len(calls), 1)
        self.assertIn("ON CONFLICT", calls[0][0])
        self.assertEqual(calls[0][1][0], "line-01")
        self.assertEqual(calls[0][1][1], "motor_state_change")

    def test_ensure_table_shape_drops_empty_incompatible_table(self) -> None:
        calls: list[tuple[str, tuple | None]] = []

        class FakeCursor:
            def __init__(self) -> None:
                self._last = None

            def execute(self, query: str, params=None) -> None:
                calls.append((query, params))
                self._last = query

            def fetchall(self):
                if "information_schema.columns" in (self._last or ""):
                    return [("asset_id",), ("parameter",), ("value",), ("gateway_time",), ("payload",)]
                return []

            def fetchone(self):
                if "COUNT(*)" in (self._last or ""):
                    return (0,)
                return None

        sink_main._ensure_table_shape(
            FakeCursor(),
            "telemetry_1s",
            {"asset_id", "parameter", "classification", "window_start", "window_end", "payload"},
        )

        self.assertTrue(any("DROP TABLE IF EXISTS" in query for query, _ in calls))

    def test_dedupe_aggregate_table_uses_window_identity(self) -> None:
        calls: list[str] = []

        class FakeCursor:
            def execute(self, query: str, params=None) -> None:  # noqa: ARG002 - test stub
                calls.append(query)

        sink_main._dedupe_aggregate_table(FakeCursor(), "telemetry_1min")

        self.assertEqual(len(calls), 1)
        self.assertIn("ROW_NUMBER()", calls[0])
        self.assertIn("PARTITION BY asset_id, parameter, window_start, window_end", calls[0])

    def test_dedupe_event_table_uses_event_identity(self) -> None:
        calls: list[str] = []

        class FakeCursor:
            def execute(self, query: str, params=None) -> None:  # noqa: ARG002 - test stub
                calls.append(query)

        sink_main._dedupe_event_table(FakeCursor(), "events")

        self.assertEqual(len(calls), 1)
        self.assertIn("ROW_NUMBER()", calls[0])
        self.assertIn("PARTITION BY asset_id, event_type, gateway_time", calls[0])


if __name__ == "__main__":
    unittest.main()
