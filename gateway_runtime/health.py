"""Health reporting and status types."""

from dataclasses import dataclass
from enum import Enum
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

    def emit(self, event: HealthEvent) -> None:
        """Record a new health event."""

    def snapshot(self) -> Dict[str, object]:
        """Return current health snapshot."""
