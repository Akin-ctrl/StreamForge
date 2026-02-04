"""Gateway runtime entrypoint (skeleton)."""

from gateway_runtime.adapter_factory import AdapterFactory
from gateway_runtime.adapter_manager import AdapterManager
from gateway_runtime.config import ConfigRepository
from gateway_runtime.health import HealthReporter
from gateway_runtime.kafka_manager import KafkaManager
from gateway_runtime.runtime import GatewayRuntime


def main() -> None:
    """Application entrypoint for Phase 1 gateway runtime."""


if __name__ == "__main__":
    main()
