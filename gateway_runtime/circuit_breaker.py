"""Circuit breaker primitive for external dependency protection."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a request is blocked because the breaker is open."""


@dataclass(frozen=True)
class CircuitBreakerSnapshot:
    """Immutable view of the current breaker state."""

    name: str
    state: str
    consecutive_failures: int
    failure_threshold: int
    open_remaining_seconds: float
    last_error: str | None


class CircuitBreaker:
    """Minimal CLOSED / OPEN / HALF_OPEN circuit breaker."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        open_duration_seconds: float = 30.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._name = name
        self._failure_threshold = max(int(failure_threshold), 1)
        self._open_duration_seconds = max(float(open_duration_seconds), 0.0)
        self._clock = clock or time.monotonic
        self._state = "closed"
        self._consecutive_failures = 0
        self._open_until = 0.0
        self._last_error: str | None = None

    def allow_request(self) -> bool:
        """Return whether the next request is allowed."""
        now = self._clock()
        if self._state == "open":
            if now >= self._open_until:
                self._state = "half_open"
                return True
            return False
        return True

    def ensure_request_allowed(self) -> None:
        """Raise when the breaker is open and the request should be blocked."""
        if not self.allow_request():
            remaining = self.remaining_open_seconds()
            raise CircuitBreakerOpenError(
                f"{self._name} circuit breaker is open for another {remaining:.1f}s"
            )

    def record_success(self) -> None:
        """Close the breaker and clear failure counters after a successful request."""
        self._state = "closed"
        self._consecutive_failures = 0
        self._open_until = 0.0
        self._last_error = None

    def record_failure(self, exc: Exception) -> None:
        """Record a failed request and open the breaker when the threshold is reached."""
        self._last_error = str(exc)
        now = self._clock()

        if self._state == "half_open":
            self._trip(now)
            return

        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._trip(now)

    def remaining_open_seconds(self) -> float:
        """Return how long the breaker will stay open."""
        if self._state != "open":
            return 0.0
        return max(self._open_until - self._clock(), 0.0)

    def snapshot(self) -> CircuitBreakerSnapshot:
        """Return a serializable snapshot for health reporting."""
        return CircuitBreakerSnapshot(
            name=self._name,
            state=self._state,
            consecutive_failures=self._consecutive_failures,
            failure_threshold=self._failure_threshold,
            open_remaining_seconds=self.remaining_open_seconds(),
            last_error=self._last_error,
        )

    def _trip(self, now: float) -> None:
        self._state = "open"
        self._consecutive_failures = self._failure_threshold
        self._open_until = now + self._open_duration_seconds
