"""Adapter manager for starting and monitoring adapters."""

from __future__ import annotations

import json
import os
import socket
from typing import Dict, List

from gateway_runtime.adapter_factory import AdapterFactory
from gateway_runtime.config import AdapterConfig
from gateway_runtime.errors import AdapterStartError


class AdapterManager:
    """
    Starts and monitors adapter containers.

    Phase 1: Manage Docker containers for adapters.
    """

    def __init__(self, factory: AdapterFactory) -> None:
        """Initialize manager with adapter factory."""
        self._factory = factory
        self._containers: Dict[str, str] = {}
        self._client = None
        self._network = None

    def start_all(self, configs: List[AdapterConfig]) -> None:
        """Start all adapters defined in config."""
        client = self._docker_client()
        network = self._resolve_network(client)

        for config in configs:
            if config.adapter_id in self._containers:
                raise AdapterStartError(f"Adapter already running: {config.adapter_id}")

            container_name = self._container_name(config.adapter_id)
            image = self._image_for(config.adapter_type)
            env = {
                "ADAPTER_CONFIG_JSON": json.dumps(config.config),
                "ADAPTER_CONFIG": json.dumps(config.config),
            }

            labels = {
                "app": "streamforge",
                "component": "adapter",
                "adapter_id": config.adapter_id,
                "adapter_type": config.adapter_type,
            }
            labels.update(self._compose_labels())

            container = self._ensure_container(
                client=client,
                name=container_name,
                image=image,
                environment=env,
                network=network,
                labels=labels,
            )

            self._containers[config.adapter_id] = container.id
            print(f"adapter_manager started {config.adapter_id} as {container.name}", flush=True)

    def stop_all(self) -> None:
        """Stop all running adapters."""
        client = self._docker_client()
        for adapter_id, container_id in list(self._containers.items()):
            self._stop_container(client, container_id)
            self._containers.pop(adapter_id, None)

    def restart(self, adapter_id: str) -> None:
        """Restart a specific adapter by ID."""
        if adapter_id not in self._containers:
            raise AdapterStartError(f"Adapter not found: {adapter_id}")

        client = self._docker_client()
        container_id = self._containers[adapter_id]
        self._stop_container(client, container_id)
        self._containers.pop(adapter_id, None)
        raise AdapterStartError(f"Adapter restart requires fresh config: {adapter_id}")

    def health(self) -> Dict[str, object]:
        """Return health status for all adapters."""
        client = self._docker_client()
        adapter_states = {}
        for adapter_id, container_id in self._containers.items():
            status = "unknown"
            try:
                container = client.containers.get(container_id)
                status = container.status
            except Exception:
                status = "missing"

            adapter_states[adapter_id] = status

        overall = "healthy" if all(state == "running" for state in adapter_states.values()) else "degraded"

        return {
            "status": overall,
            "adapters": adapter_states,
        }

    def _docker_client(self):
        if self._client is None:
            try:
                import docker  # type: ignore
            except ModuleNotFoundError as exc:
                raise AdapterStartError("docker SDK is required to manage adapters") from exc

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
                restart_policy={"Name": "unless-stopped"},
            )

    def _stop_container(self, client, container_id: str) -> None:
        try:
            container = client.containers.get(container_id)
            container.stop(timeout=5)
            container.remove()
        except Exception:
            return None

    @staticmethod
    def _container_name(adapter_id: str) -> str:
        return f"sf-adapter-{adapter_id}"

    @staticmethod
    def _image_for(adapter_type: str) -> str:
        if adapter_type == "modbus_tcp":
            return "streamforge/adapter_modbus_tcp:dev"

        raise AdapterStartError(f"Unsupported adapter type: {adapter_type}")

    @staticmethod
    def _compose_labels() -> Dict[str, str]:
        project = os.getenv("COMPOSE_PROJECT_NAME") or os.getenv("DOCKER_COMPOSE_PROJECT") or "deploy"
        return {
            "com.docker.compose.project": project,
            "com.docker.compose.service": "adapter_modbus_tcp",
            "com.docker.compose.oneoff": "False",
        }
