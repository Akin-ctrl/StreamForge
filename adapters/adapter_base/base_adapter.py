"""Abstract base adapter class."""

from __future__ import annotations

import signal
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import os
from threading import Event, Lock
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
        self._poll_interval_lock = Lock()
        self._base_poll_interval_s = max(self._parse_poll_interval_ms(config.get("poll_interval_ms", 1000)) / 1000.0, 0.0)
        self._poll_interval_s = self._base_poll_interval_s
        self._throttle_mode = "normal"
        self._throttle_multiplier = 1.0
        self._throttle_reason: str | None = None
        self._publisher: KafkaPublisher | None = None
        self._adapter_id = str(config.get("adapter_id") or os.getenv("ADAPTER_ID", self.__class__.__name__.lower()))
        self._adapter_type = str(config.get("adapter_type") or os.getenv("ADAPTER_TYPE", self.__class__.__name__))
        self._http_host = os.getenv("ADAPTER_HEALTH_HOST", "0.0.0.0")
        self._http_port = int(os.getenv("ADAPTER_HEALTH_PORT", "8080"))
        initial_topic = None
        output = config.get("output")
        if isinstance(output, dict):
            initial_topic = output.get("topic")
        self._health: Dict[str, object] = {
            "status": "initialized",
            "adapter_id": self._adapter_id,
            "adapter_type": self._adapter_type,
            "adapter": self.__class__.__name__,
            "connected": False,
            "running": False,
            "base_poll_interval_ms": int(self._base_poll_interval_s * 1000),
            "poll_interval_ms": int(self._poll_interval_s * 1000),
            "throttle_mode": self._throttle_mode,
            "throttle_multiplier": self._throttle_multiplier,
            "throttle_reason": self._throttle_reason,
            "throttle_updated_at": None,
            "throttle_transitions_total": 0,
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

    @staticmethod
    def _parse_poll_interval_ms(value: object) -> float:
        """Parse poll interval config while tolerating blank UI form values."""
        if value in (None, ""):
            return 1000.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 1000.0

    def run(self) -> None:
        """Run adapter lifecycle until a stop signal or a fatal error occurs."""
        previous_handlers = self._install_signal_handlers()
        try:
            self._set_status("starting", connected=False, running=False, last_error=None)
            self.connect()
            self._set_status("healthy", connected=True, running=True, last_error=None)

            while not self._stop_event.is_set():
                self.run_once()
                if self._stop_event.wait(self._effective_poll_interval_s()):
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

    def set_runtime_throttle(self, mode: str, multiplier: float, reason: str | None = None) -> Dict[str, object]:
        """Apply a runtime throttle overlay without mutating base config."""
        normalized_mode = str(mode or "normal").strip().lower()
        normalized_multiplier = max(float(multiplier or 1.0), 1.0)
        if normalized_mode == "normal":
            normalized_multiplier = 1.0
            reason = None

        with self._poll_interval_lock:
            changed = (
                normalized_mode != self._throttle_mode
                or normalized_multiplier != self._throttle_multiplier
                or reason != self._throttle_reason
            )
            self._throttle_mode = normalized_mode
            self._throttle_multiplier = normalized_multiplier
            self._throttle_reason = reason
            self._poll_interval_s = self._base_poll_interval_s * self._throttle_multiplier
            self._health["poll_interval_ms"] = int(self._poll_interval_s * 1000)
            self._health["throttle_mode"] = self._throttle_mode
            self._health["throttle_multiplier"] = self._throttle_multiplier
            self._health["throttle_reason"] = self._throttle_reason
            self._health["throttle_updated_at"] = self._utcnow()
            if changed:
                self._health["throttle_transitions_total"] = int(self._health.get("throttle_transitions_total", 0)) + 1

        return {
            "status": "ok",
            "adapter_id": self._adapter_id,
            "throttle_mode": self._throttle_mode,
            "throttle_multiplier": self._throttle_multiplier,
            "effective_poll_interval_ms": int(self._effective_poll_interval_s() * 1000),
            "reason": self._throttle_reason,
        }

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

    def metrics(self) -> str:
        """Return Prometheus-formatted adapter metrics."""
        health = self.health()
        labels = f'adapter_id="{self._adapter_id}",adapter_type="{self._adapter_type}"'
        lines = [
            "# TYPE adapter_up gauge",
            f"adapter_up{{{labels}}} {1 if health.get('status') in {'healthy', 'degraded', 'starting'} else 0}",
            "# TYPE adapter_connected gauge",
            f"adapter_connected{{{labels}}} {1 if health.get('connected') else 0}",
            "# TYPE adapter_published_messages_total counter",
            f"adapter_published_messages_total{{{labels}}} {int(health.get('published_messages', 0))}",
            "# TYPE adapter_publish_failures_total counter",
            f"adapter_publish_failures_total{{{labels}}} {int(health.get('publish_failures', 0))}",
            "# TYPE adapter_poll_interval_ms gauge",
            f"adapter_poll_interval_ms{{{labels}}} {int(health.get('poll_interval_ms', 0))}",
            "# TYPE adapter_throttle_multiplier gauge",
            f"adapter_throttle_multiplier{{{labels}}} {float(health.get('throttle_multiplier', 1.0))}",
            "# TYPE adapter_throttle_active gauge",
            f"adapter_throttle_active{{{labels}}} {1 if str(health.get('throttle_mode', 'normal')) != 'normal' else 0}",
            "# TYPE adapter_throttle_transitions_total counter",
            f"adapter_throttle_transitions_total{{{labels}}} {int(health.get('throttle_transitions_total', 0))}",
        ]
        for metric_name in (
            "modbus_connect_failures",
            "modbus_read_failures",
            "modbus_reconnects",
            "modbus_batch_failures",
            "modbus_register_batch_failures",
            "modbus_coil_batch_failures",
        ):
            if metric_name in health:
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(f"{metric_name}{{{labels}}} {int(health.get(metric_name, 0))}")
        return "\n".join(lines) + "\n"

    @property
    def http_host(self) -> str:
        return self._http_host

    @property
    def http_port(self) -> int:
        return self._http_port

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

    def _effective_poll_interval_s(self) -> float:
        with self._poll_interval_lock:
            return self._poll_interval_s
