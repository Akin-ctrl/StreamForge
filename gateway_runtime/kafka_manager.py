"""Kafka manager for local embedded Kafka (KRaft)."""

from __future__ import annotations

from typing import Dict
import socket
import time

from gateway_runtime.errors import KafkaError


class KafkaManager:
    """
    Manages local Kafka lifecycle (embedded single-node KRaft).

    Phase 1 behavior:
    - Start/stop Kafka container
    - Provide bootstrap address
    """

    def __init__(self, bootstrap: str) -> None:
        """Initialize with local Kafka bootstrap address."""
        self._bootstrap = bootstrap
        self._host, self._port = self._parse_bootstrap(bootstrap)

    def start(self) -> None:
        """Start local Kafka (container or process)."""
        if not self._wait_for_port(timeout_s=60):
            raise KafkaError(f"Kafka not reachable at {self._bootstrap}")

    def stop(self) -> None:
        """Stop local Kafka."""
        return None

    def health(self) -> Dict[str, object]:
        """Return Kafka health status."""
        reachable = self._wait_for_port(timeout_s=1)
        return {
            "status": "healthy" if reachable else "failed",
            "bootstrap": self._bootstrap,
            "reachable": reachable,
        }

    def _parse_bootstrap(self, bootstrap: str) -> tuple[str, int]:
        """Parse host and port from bootstrap string (host:port)."""
        if ":" not in bootstrap:
            raise KafkaError(f"Invalid bootstrap format: {bootstrap}")

        host, port_str = bootstrap.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError as exc:
            raise KafkaError(f"Invalid port in bootstrap: {bootstrap}") from exc

        return host, port

    def _wait_for_port(self, timeout_s: int) -> bool:
        """Check if Kafka port is reachable within timeout."""
        end_time = time.time() + timeout_s
        while time.time() < end_time:
            if self._can_connect():
                return True
            time.sleep(0.2)
        return False

    def _can_connect(self) -> bool:
        """Attempt a TCP connection to the Kafka host:port."""
        try:
            with socket.create_connection((self._host, self._port), timeout=1):
                return True
        except OSError:
            return False
