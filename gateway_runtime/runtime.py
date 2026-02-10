"""Gateway runtime facade for Phase 1."""

from typing import Dict

from gateway_runtime.adapter_manager import AdapterManager
from gateway_runtime.config import ConfigRepository
from gateway_runtime.health import HealthReporter
from gateway_runtime.kafka_manager import KafkaManager


class GatewayRuntime:
    """
    Facade for the Phase 1 gateway runtime.

    Responsibilities:
    - Orchestrate Kafka, adapters, and health reporting
    - Load static config (Phase 1 only)
    - Start/stop lifecycle
    """

    def __init__(
        self,
        config_repo: ConfigRepository,
        kafka: KafkaManager,
        adapters: AdapterManager,
        health: HealthReporter,
    ) -> None:
        """Initialize runtime with required managers."""
        self._config_repo = config_repo
        self._kafka = kafka
        self._adapters = adapters
        self._health = health

    def start(self) -> None:
        """Start all runtime components in correct order."""
        print("gateway_runtime starting", flush=True)
        config = self._config_repo.load()
        print("gateway_runtime config loaded", flush=True)
        self._kafka.start()
        print("gateway_runtime kafka ready", flush=True)
        self._adapters.start_all(config.adapters)
        print("gateway_runtime adapters started", flush=True)

    def stop(self) -> None:
        """Stop all runtime components gracefully."""
        print("gateway_runtime stopping", flush=True)
        self._adapters.stop_all()
        self._kafka.stop()
        print("gateway_runtime stopped", flush=True)

    def reload_config(self) -> None:
        """Reload configuration and apply changes (Phase 2+)."""

    def health_snapshot(self) -> Dict[str, object]:
        """Return aggregated health snapshot for the gateway."""
        return {
            "kafka": self._kafka.health(),
            "adapters": self._adapters.health(),
        }
