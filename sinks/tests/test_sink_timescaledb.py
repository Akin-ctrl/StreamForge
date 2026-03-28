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


if __name__ == "__main__":
    unittest.main()
