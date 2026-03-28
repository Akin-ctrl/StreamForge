"""Tests for circuit breaker behavior."""

from __future__ import annotations

import unittest

from gateway_runtime.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class CircuitBreakerTests(unittest.TestCase):
    def test_opens_after_threshold_and_blocks_until_timeout(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker("test", failure_threshold=3, open_duration_seconds=10, clock=clock.now)

        breaker.record_failure(RuntimeError("boom-1"))
        breaker.record_failure(RuntimeError("boom-2"))
        self.assertTrue(breaker.allow_request())

        breaker.record_failure(RuntimeError("boom-3"))
        self.assertFalse(breaker.allow_request())
        self.assertEqual(breaker.snapshot().state, "open")
        self.assertAlmostEqual(breaker.remaining_open_seconds(), 10.0)

        with self.assertRaises(CircuitBreakerOpenError):
            breaker.ensure_request_allowed()

    def test_transitions_to_half_open_then_closed_on_success(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker("test", failure_threshold=2, open_duration_seconds=5, clock=clock.now)

        breaker.record_failure(RuntimeError("boom-1"))
        breaker.record_failure(RuntimeError("boom-2"))
        self.assertEqual(breaker.snapshot().state, "open")

        clock.advance(5)
        self.assertTrue(breaker.allow_request())
        self.assertEqual(breaker.snapshot().state, "half_open")

        breaker.record_success()
        snapshot = breaker.snapshot()
        self.assertEqual(snapshot.state, "closed")
        self.assertEqual(snapshot.consecutive_failures, 0)
        self.assertIsNone(snapshot.last_error)

    def test_half_open_failure_reopens_breaker(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker("test", failure_threshold=2, open_duration_seconds=7, clock=clock.now)

        breaker.record_failure(RuntimeError("boom-1"))
        breaker.record_failure(RuntimeError("boom-2"))
        clock.advance(7)
        self.assertTrue(breaker.allow_request())
        self.assertEqual(breaker.snapshot().state, "half_open")

        breaker.record_failure(RuntimeError("boom-again"))
        snapshot = breaker.snapshot()
        self.assertEqual(snapshot.state, "open")
        self.assertEqual(snapshot.consecutive_failures, 2)
        self.assertEqual(snapshot.last_error, "boom-again")


if __name__ == "__main__":
    unittest.main()
