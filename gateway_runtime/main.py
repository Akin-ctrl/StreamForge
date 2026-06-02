"""Gateway runtime entrypoint."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import threading

from gateway_runtime.adapter_factory import AdapterFactory
from gateway_runtime.adapter_manager import AdapterManager
from gateway_runtime.config import ConfigRepository, ControlPlaneConfigRepository
from gateway_runtime.health import HealthReporter
from gateway_runtime.kafka_manager import KafkaManager
from gateway_runtime.overflow import OverflowManager
from gateway_runtime.runtime import GatewayRuntime
from gateway_runtime.errors import ConfigError
from gateway_runtime.health_server import HealthServer
from gateway_runtime.logging_utils import configure_json_logging
from gateway_runtime.sink_manager import SinkManager


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
    configure_json_logging(os.getenv("LOG_LEVEL", "INFO"))
    config_path = os.getenv("GATEWAY_CONFIG")
    control_plane_url = os.getenv("CONTROL_PLANE_URL")
    control_plane_gateway_id = os.getenv("CONTROL_PLANE_GATEWAY_ID")
    control_plane_token = os.getenv("CONTROL_PLANE_TOKEN")
    control_plane_enrollment_token = os.getenv("CONTROL_PLANE_ENROLLMENT_TOKEN")
    control_plane_gateway_hostname = os.getenv("CONTROL_PLANE_GATEWAY_HOSTNAME") or socket.gethostname()
    control_plane_cache_path = os.getenv("GATEWAY_CONFIG_CACHE", "/data/config/gateway.json")
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
            if control_plane_enrollment_token:
                control_plane_gateway_id = control_plane_gateway_hostname
            else:
                raise ConfigError("CONTROL_PLANE_GATEWAY_ID is required when CONTROL_PLANE_URL is set")

        enrollment_hardware_info = {
            "runtime": "gateway_runtime",
            "hostname": control_plane_gateway_hostname,
        }
        raw_hardware_info = os.getenv("CONTROL_PLANE_GATEWAY_HARDWARE_INFO")
        if raw_hardware_info:
            try:
                parsed_hardware_info = json.loads(raw_hardware_info)
            except json.JSONDecodeError as exc:
                raise ConfigError("CONTROL_PLANE_GATEWAY_HARDWARE_INFO must be valid JSON") from exc
            if not isinstance(parsed_hardware_info, dict):
                raise ConfigError("CONTROL_PLANE_GATEWAY_HARDWARE_INFO must be a JSON object")
            enrollment_hardware_info.update(parsed_hardware_info)

        config_repo = ControlPlaneConfigRepository(
            base_url=control_plane_url,
            gateway_id=control_plane_gateway_id,
            token=control_plane_token,
            enrollment_token=control_plane_enrollment_token,
            enrollment_hostname=control_plane_gateway_hostname,
            enrollment_hardware_info=enrollment_hardware_info,
            cache_path=control_plane_cache_path,
        )
    else:
        config_repo = ConfigRepository(config_path)
    kafka = KafkaManager(kafka_bootstrap)
    adapters = AdapterManager(AdapterFactory())
    sinks = SinkManager()
    health = HealthReporter()
    overflow = OverflowManager(
        gateway_id=control_plane_gateway_id or "gateway",
        kafka_manager=kafka,
        adapter_manager=adapters,
    )

    runtime = GatewayRuntime(
        config_repo=config_repo,
        kafka=kafka,
        adapters=adapters,
        sinks=sinks,
        health=health,
        overflow=overflow,
    )

    server = HealthServer(health_host, health_port_int, runtime.health_snapshot, runtime.metrics_snapshot)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    asyncio.run(_run(runtime))


if __name__ == "__main__":
    main()
