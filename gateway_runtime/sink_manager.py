"""Sink manager for starting and monitoring sink containers."""

from __future__ import annotations

import json
import os
import socket
from typing import Dict, List

from gateway_runtime.config import SinkConfig
from gateway_runtime.errors import AdapterStartError


class SinkManager:
    """Starts and monitors sink containers from gateway configuration."""

    def __init__(self) -> None:
        self._containers: Dict[str, str] = {}
        self._client = None
        self._network = None

    def start_all(self, configs: List[SinkConfig]) -> None:
        """Start all configured sinks in active status."""
        client = self._docker_client()
        network = self._resolve_network(client)

        for config in configs:
            if config.status != "active":
                continue
            self.start_sink(config, client=client, network=network)

    def stop_all(self) -> None:
        """Stop all running sinks."""
        client = self._docker_client()
        for sink_id, container_id in list(self._containers.items()):
            self._stop_container(client, container_id)
            self._containers.pop(sink_id, None)

    def start_sink(self, config: SinkConfig, client=None, network: str | None = None) -> None:
        """Start single sink container."""
        if config.sink_id in self._containers:
            self.stop_sink(config.sink_id)

        client = client or self._docker_client()
        network = network or self._resolve_network(client)

        container_name = self._container_name(config.sink_id)
        image = self._image_for(config.sink_type)
        env = {
            "SINK_CONFIG": json.dumps(config.config),
        }

        labels = {
            "app": "streamforge",
            "component": "sink",
            "sink_id": config.sink_id,
            "sink_type": config.sink_type,
        }
        labels.update(self._compose_labels())

        command = self._command_for(config.sink_type)

        container = self._ensure_container(
            client=client,
            name=container_name,
            image=image,
            environment=env,
            network=network,
            labels=labels,
            command=command,
        )
        self._containers[config.sink_id] = container.id
        print(f"sink_manager started {config.sink_id} as {container.name}", flush=True)

    def stop_sink(self, sink_id: str) -> None:
        """Stop single sink by id."""
        if sink_id not in self._containers:
            return
        client = self._docker_client()
        self._stop_container(client, self._containers[sink_id])
        self._containers.pop(sink_id, None)
        print(f"sink_manager stopped {sink_id}", flush=True)

    def health(self) -> Dict[str, object]:
        """Return sink health status."""
        client = self._docker_client()
        sink_states = {}
        for sink_id, container_id in self._containers.items():
            status = "unknown"
            try:
                container = client.containers.get(container_id)
                status = container.status
            except Exception:
                status = "missing"
            sink_states[sink_id] = status

        overall = "healthy" if all(state == "running" for state in sink_states.values()) else "degraded"
        if not sink_states:
            overall = "healthy"

        return {
            "status": overall,
            "sinks": sink_states,
        }

    def _docker_client(self):
        if self._client is None:
            try:
                import docker  # type: ignore
            except ModuleNotFoundError as exc:
                raise AdapterStartError("docker SDK is required to manage sinks") from exc

            self._client = docker.from_env()
        return self._client

    def _resolve_network(self, client) -> str:
        if self._network:
            return self._network

        env_network = os.getenv("DOCKER_NETWORK")
        if env_network:
            self._network = env_network
            return self._network

        try:
            container = client.containers.get(socket.gethostname())
            networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
            if networks:
                self._network = next(iter(networks.keys()))
                return self._network
        except Exception:
            pass

        self._network = "bridge"
        return self._network

    def _ensure_container(
        self,
        client,
        name: str,
        image: str,
        environment: Dict[str, str],
        network: str,
        labels: Dict[str, str],
        command: list[str],
    ):
        try:
            container = client.containers.get(name)
            if container.status != "running":
                container.start()
            return container
        except Exception:
            return client.containers.run(
                image=image,
                name=name,
                detach=True,
                environment=environment,
                network=network,
                labels=labels,
                command=command,
                restart_policy={"Name": "unless-stopped"},
            )

    @staticmethod
    def _stop_container(client, container_id: str) -> None:
        try:
            container = client.containers.get(container_id)
            container.stop(timeout=5)
            container.remove()
        except Exception:
            return None

    @staticmethod
    def _container_name(sink_id: str) -> str:
        return f"sf-sink-{sink_id}"

    @staticmethod
    def _image_for(sink_type: str) -> str:
        if sink_type in {"timescaledb", "sink-timescaledb", "sink_timescaledb"}:
            return os.getenv("SINK_TIMESCALEDB_IMAGE", "streamforge/gateway_runtime:dev")
        raise AdapterStartError(f"Unsupported sink type: {sink_type}")

    @staticmethod
    def _command_for(sink_type: str) -> list[str]:
        if sink_type in {"timescaledb", "sink-timescaledb", "sink_timescaledb"}:
            return ["python", "-m", "sinks.sink_timescaledb.main"]
        raise AdapterStartError(f"Unsupported sink type: {sink_type}")

    @staticmethod
    def _compose_labels() -> Dict[str, str]:
        project = os.getenv("COMPOSE_PROJECT_NAME") or os.getenv("DOCKER_COMPOSE_PROJECT") or "deploy"
        return {
            "com.docker.compose.project": project,
            "com.docker.compose.service": "sink_timescaledb",
            "com.docker.compose.oneoff": "False",
        }
