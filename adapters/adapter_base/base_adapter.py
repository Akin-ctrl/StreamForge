"""Abstract base adapter class."""

from __future__ import annotations

import signal
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from threading import Event
from typing import Dict

from adapters.adapter_base.kafka_publisher import KafkaPublisher


class BaseAdapter(ABC):
    """
    Shared adapter runtime contract.

    The gateway runtime owns adapter containers. Inside each adapter container,
    this class owns the synchronous lifecycle: connect, poll, transform,
    publish, and graceful shutdown.
    """

    def __init__(self, config: dict) -> None:
        """Initialize adapter with validated config."""
        self.config = config
        self._stop_event = Event()
        self._poll_interval_s = max(float(config.get("poll_interval_ms", 1000)) / 1000.0, 0.0)
        self._publisher: KafkaPublisher | None = None
        initial_topic = None
        output = config.get("output")
        if isinstance(output, dict):
            initial_topic = output.get("topic")
        self._health: Dict[str, object] = {
            "status": "initialized",
            "adapter": self.__class__.__name__,
            "connected": False,
            "running": False,
            "poll_interval_ms": int(self._poll_interval_s * 1000),
            "last_poll_at": None,
            "last_publish_at": None,
            "last_publish_topic": initial_topic,
            "last_publish_key": None,
            "last_publish_partition": None,
            "last_publish_offset": None,
            "published_messages": 0,
            "publish_failures": 0,
            "last_error": None,
        }

    def run(self) -> None:
        """Run adapter lifecycle until a stop signal or a fatal error occurs."""
        previous_handlers = self._install_signal_handlers()
        try:
            self._set_status("starting", connected=False, running=False, last_error=None)
            self.connect()
            self._set_status("healthy", connected=True, running=True, last_error=None)

            while not self._stop_event.is_set():
                self.run_once()
                if self._stop_event.wait(self._poll_interval_s):
                    break
        except Exception as exc:
            self._set_status("failed", running=False, last_error=str(exc))
            raise
        finally:
            try:
                self.disconnect()
            finally:
                if self._publisher is not None:
                    self._publisher.close()
                connected = False
                status = "stopped" if self._health.get("status") != "failed" else "failed"
                self._set_status(status, connected=connected, running=False)
                self._restore_signal_handlers(previous_handlers)

    def run_once(self) -> Dict[str, object]:
        """Execute a single lifecycle iteration."""
        polled_at = self._utcnow()
        raw = self.poll()
        self._health["last_poll_at"] = polled_at
        message = self.transform(raw)
        self.publish(message)
        self._health["last_publish_at"] = self._utcnow()
        self._set_status("healthy", connected=True, running=True, last_error=None)
        return message

    def stop(self) -> None:
        """Request graceful shutdown."""
        self._stop_event.set()

    @abstractmethod
    def connect(self) -> None:
        """Connect to device or data source."""

    def disconnect(self) -> None:
        """Release protocol and broker resources."""

    @abstractmethod
    def poll(self) -> Dict[str, object]:
        """Read raw data from device."""

    @abstractmethod
    def transform(self, raw: Dict[str, object]) -> Dict[str, object]:
        """Normalize raw data into standard message format."""

    def publish(self, message: Dict[str, object]) -> None:
        """Publish normalized message using the shared adapter Kafka publisher."""
        if self._publisher is None:
            self._publisher = KafkaPublisher(self.config)
        publish_metadata = self._publisher.publish(message)
        publish_health = self._publisher.health()
        self._health["last_publish_topic"] = publish_metadata["topic"]
        self._health["last_publish_key"] = publish_metadata["key"]
        self._health["last_publish_partition"] = publish_metadata["partition"]
        self._health["last_publish_offset"] = publish_metadata["offset"]
        self._health["published_messages"] = publish_health["published_messages"]
        self._health["publish_failures"] = publish_health["publish_failures"]
        self._health["last_error"] = publish_health["last_error"]

    def health(self) -> Dict[str, object]:
        """Return adapter health status."""
        snapshot = dict(self._health)
        if self._publisher is not None:
            snapshot.update(self._publisher.health())
        return snapshot

    def _handle_shutdown_signal(self, signum, _frame) -> None:
        signal_name = signal.Signals(signum).name
        self._set_status("stopping", running=False, last_error=None)
        self._health["last_signal"] = signal_name
        self.stop()

    def _install_signal_handlers(self) -> Dict[int, object]:
        previous_handlers: Dict[int, object] = {}
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, self._handle_shutdown_signal)
        return previous_handlers

    @staticmethod
    def _restore_signal_handlers(previous_handlers: Dict[int, object]) -> None:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)

    def _set_status(self, status: str, **updates: object) -> None:
        self._health["status"] = status
        self._health.update(updates)

    @staticmethod
    def _utcnow() -> str:
        return datetime.now(timezone.utc).isoformat()
