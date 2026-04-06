"""Health reporting and status types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import threading
from typing import Dict


class AdapterState(str, Enum):
    """Health state for adapters and components."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True)
class HealthEvent:
    """Health event emitted by a component."""

    component: str
    status: AdapterState
    details: Dict[str, object]


class HealthReporter:
    """
    Aggregates component health and exposes it to the gateway.

    Follows Observer pattern: managers emit events, reporter aggregates.
    """

    def __init__(self) -> None:
        """Initialize reporter with empty state."""
        self._lock = threading.Lock()
        self._events: dict[str, HealthEvent] = {}

    def emit(self, event: HealthEvent) -> None:
        """Record a new health event."""
        with self._lock:
            self._events[event.component] = event

    def snapshot(self) -> Dict[str, object]:
        """Return current health snapshot."""
        with self._lock:
            events = dict(self._events)
        if not events:
            return {"status": "unknown", "components": {}}

        statuses = [event.status for event in events.values()]
        overall = AdapterState.HEALTHY
        if any(status == AdapterState.FAILED for status in statuses):
            overall = AdapterState.FAILED
        elif any(status == AdapterState.DEGRADED for status in statuses):
            overall = AdapterState.DEGRADED
        return {
            "status": overall.value,
            "components": {
                name: {"status": event.status.value, "details": event.details}
                for name, event in events.items()
            },
        }
