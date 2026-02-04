"""Kafka manager for local embedded Kafka (KRaft)."""

from typing import Dict


class KafkaManager:
    """
    Manages local Kafka lifecycle (embedded single-node KRaft).

    Phase 1 behavior:
    - Start/stop Kafka container
    - Provide bootstrap address
    """

    def __init__(self, bootstrap: str) -> None:
        """Initialize with local Kafka bootstrap address."""

    def start(self) -> None:
        """Start local Kafka (container or process)."""

    def stop(self) -> None:
        """Stop local Kafka."""

    def health(self) -> Dict[str, object]:
        """Return Kafka health status."""
