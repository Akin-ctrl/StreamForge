"""Gateway runtime entrypoint."""

from __future__ import annotations

import asyncio
import os
import threading

from gateway_runtime.adapter_factory import AdapterFactory
from gateway_runtime.adapter_manager import AdapterManager
from gateway_runtime.config import ConfigRepository, ControlPlaneConfigRepository
from gateway_runtime.health import HealthReporter
from gateway_runtime.kafka_manager import KafkaManager
from gateway_runtime.runtime import GatewayRuntime
from gateway_runtime.errors import ConfigError
from gateway_runtime.health_server import HealthServer


async def _run(runtime: GatewayRuntime) -> None:
    """Run the gateway runtime and keep the loop alive."""
    runtime.start()
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        runtime.stop()


def main() -> None:
    """Application entrypoint for the gateway runtime."""
    config_path = os.getenv("GATEWAY_CONFIG")
    control_plane_url = os.getenv("CONTROL_PLANE_URL")
    control_plane_gateway_id = os.getenv("CONTROL_PLANE_GATEWAY_ID")
    control_plane_token = os.getenv("CONTROL_PLANE_TOKEN")
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP")
    health_host = os.getenv("HEALTH_HOST")
    health_port = os.getenv("HEALTH_PORT")

    if not config_path and not control_plane_url:
        raise ConfigError("Set GATEWAY_CONFIG or CONTROL_PLANE_URL")
    if not kafka_bootstrap:
        raise ConfigError("KAFKA_BOOTSTRAP is required")
    if not health_host:
        raise ConfigError("HEALTH_HOST is required")
    if not health_port:
        raise ConfigError("HEALTH_PORT is required")

    health_port_int = int(health_port)

    if control_plane_url:
        if not control_plane_gateway_id:
            raise ConfigError("CONTROL_PLANE_GATEWAY_ID is required when CONTROL_PLANE_URL is set")
        if not control_plane_token:
            raise ConfigError("CONTROL_PLANE_TOKEN is required when CONTROL_PLANE_URL is set")

        config_repo = ControlPlaneConfigRepository(
            base_url=control_plane_url,
            gateway_id=control_plane_gateway_id,
            token=control_plane_token,
        )
    else:
        config_repo = ConfigRepository(config_path)
    kafka = KafkaManager(kafka_bootstrap)
    adapters = AdapterManager(AdapterFactory())
    health = HealthReporter()

    runtime = GatewayRuntime(
        config_repo=config_repo,
        kafka=kafka,
        adapters=adapters,
        health=health,
    )

    server = HealthServer(health_host, health_port_int, runtime.health_snapshot)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    asyncio.run(_run(runtime))


if __name__ == "__main__":
    main()
