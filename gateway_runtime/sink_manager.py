"""Sink manager for starting and monitoring sink containers."""

from __future__ import annotations

import json
import logging
import os
import socket
from typing import Dict, List

from gateway_runtime.config import SinkConfig
from gateway_runtime.docker_types import DockerClientLike, DockerContainerLike
from gateway_runtime.errors import AdapterStartError

try:
    from docker import errors as docker_errors  # type: ignore
except ModuleNotFoundError:
    docker_errors = None


logger = logging.getLogger(__name__)


class SinkManager:
    """Starts and monitors sink containers from gateway configuration."""

    def __init__(self) -> None:
        self._containers: Dict[str, str] = {}
        self._client: DockerClientLike | None = None
        self._network: str | None = None

    def start_all(self, configs: List[SinkConfig]) -> None:
        """Start all configured sinks in active status."""
        client = self._docker_client()
        network = self._resolve_network(client)
        desired_ids = {config.sink_id for config in configs if config.status == "active"}
        self._prune_orphaned_containers(client, desired_ids)

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

    def start_sink(
        self,
        config: SinkConfig,
        client: DockerClientLike | None = None,
        network: str | None = None,
    ) -> None:
        """Start single sink container."""
        if config.sink_id in self._containers:
            self.stop_sink(config.sink_id)

        client = client or self._docker_client()
        network = network or self._resolve_network(client)

        container_name = self._container_name(config.sink_id)
        image = self._image_for(config.sink_type)
        env = {
            "SINK_CONFIG": json.dumps(config.config),
            "SINK_TOPIC": str(config.config.get("topic", "telemetry.clean")),
        }
        self._inject_shared_env(env, config.config)

        labels = {
            "app": "streamforge",
            "component": "sink",
            "streamforge.managed-by": "gateway_runtime",
            "sink_id": config.sink_id,
            "sink_type": config.sink_type,
        }
        labels.update(self._compose_labels(config.sink_type))

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
        logger.info("sink manager started %s as %s", config.sink_id, container.name)

    def stop_sink(self, sink_id: str) -> None:
        """Stop single sink by id."""
        if sink_id not in self._containers:
            return
        client = self._docker_client()
        self._stop_container(client, self._containers[sink_id])
        self._containers.pop(sink_id, None)
        logger.info("sink manager stopped %s", sink_id)

    def health(self) -> Dict[str, object]:
        """Return sink health status."""
        client = self._docker_client()
        sink_states = {}
        for sink_id, container_id in self._containers.items():
            container = self._get_container(client, container_id, context=f"reading health for sink {sink_id}")
            status = container.status if container is not None else "missing"
            sink_states[sink_id] = status

        overall = "healthy" if all(state == "running" for state in sink_states.values()) else "degraded"
        if not sink_states:
            overall = "healthy"

        return {
            "status": overall,
            "sinks": sink_states,
        }

    def _docker_client(self) -> DockerClientLike:
        """Create the optional Docker client lazily for sink management."""
        if self._client is None:
            try:
                import docker  # type: ignore
            except ModuleNotFoundError as exc:
                raise AdapterStartError("docker SDK is required to manage sinks") from exc

            self._client = docker.from_env()
        return self._client

    def _resolve_network(self, client: DockerClientLike) -> str:
        """Infer the Docker network sinks should join in the current runtime."""
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
        except Exception as exc:
            logger.warning("sink manager could not infer runtime docker network; falling back to bridge: %s", exc)

        self._network = "bridge"
        return self._network

    def _ensure_container(
        self,
        client: DockerClientLike,
        name: str,
        image: str,
        environment: Dict[str, str],
        network: str,
        labels: Dict[str, str],
        command: list[str],
    ) -> DockerContainerLike:
        """Replace any stale sink container and start a fresh one."""
        container = self._get_container(client, name, context=f"checking for existing sink container {name}")
        if container is not None:
            self._stop_container(client, container.id)

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

    def _prune_orphaned_containers(self, client: DockerClientLike, desired_ids: set[str]) -> None:
        """Remove managed sink containers that are not part of the desired sink set."""
        for container in self._list_managed_containers(client):
            sink_id = self._managed_sink_id(container)
            if sink_id is None or sink_id in desired_ids:
                continue
            logger.info(
                "sink manager pruning orphaned managed container %s for sink %s",
                getattr(container, "name", "<unknown>"),
                sink_id,
            )
            self._stop_container(client, container.id)

    def _list_managed_containers(self, client: DockerClientLike) -> list[DockerContainerLike]:
        try:
            return list(client.containers.list(all=True))
        except Exception as exc:
            logger.warning("sink manager failed to list managed containers: %s", exc)
            return []

    def _managed_sink_id(self, container: DockerContainerLike) -> str | None:
        if not self._is_managed_container(container):
            return None
        labels = container.labels or {}
        sink_id = labels.get("sink_id")
        if isinstance(sink_id, str) and sink_id.strip():
            return sink_id.strip()
        name = getattr(container, "name", "").lstrip("/")
        prefix = "sf-sink-"
        if name.startswith(prefix):
            return name[len(prefix) :]
        return None

    def _is_managed_container(self, container: DockerContainerLike) -> bool:
        labels = container.labels or {}
        name = getattr(container, "name", "").lstrip("/")
        if labels.get("component") != "sink":
            return False
        if labels.get("streamforge.managed-by") == "gateway_runtime":
            return self._matches_project(labels)
        if labels.get("app") == "streamforge":
            return self._matches_project(labels)
        return name.startswith("sf-sink-")

    @staticmethod
    def _matches_project(labels: Dict[str, str]) -> bool:
        project = labels.get("com.docker.compose.project")
        if not project:
            return True
        return project == SinkManager._compose_project()

    @staticmethod
    def _is_docker_not_found(exc: Exception) -> bool:
        return bool(docker_errors is not None and isinstance(exc, docker_errors.NotFound))

    def _get_container(
        self,
        client: DockerClientLike,
        container_ref: str,
        *,
        context: str,
    ) -> DockerContainerLike | None:
        """Resolve one sink container while preserving not-found semantics."""
        try:
            return client.containers.get(container_ref)
        except Exception as exc:
            if self._is_docker_not_found(exc):
                return None
            logger.warning("sink manager failed to resolve container %s while %s: %s", container_ref, context, exc)
            return None

    def _stop_container(self, client: DockerClientLike, container_id: str) -> None:
        container = self._get_container(client, container_id, context=f"stopping sink container {container_id}")
        if container is None:
            return
        try:
            container.stop(timeout=5)
            container.remove()
        except Exception as exc:
            logger.warning("sink manager failed to stop container %s cleanly: %s", container_id, exc)

    @staticmethod
    def _container_name(sink_id: str) -> str:
        return f"sf-sink-{sink_id}"

    @staticmethod
    def _image_for(sink_type: str) -> str:
        if sink_type in {"timescaledb", "sink-timescaledb", "sink_timescaledb"}:
            return os.getenv("SINK_TIMESCALEDB_IMAGE", "streamforge/gateway_runtime:dev")
        if sink_type in {"kafka", "sink-kafka", "sink_kafka"}:
            return os.getenv("SINK_KAFKA_IMAGE", "streamforge/gateway_runtime:dev")
        if sink_type in {"http", "sink-http", "sink_http"}:
            return os.getenv("SINK_HTTP_IMAGE", "streamforge/gateway_runtime:dev")
        if sink_type in {"alert_router", "sink-alert-router", "sink_alert_router"}:
            return os.getenv("SINK_ALERT_ROUTER_IMAGE", "streamforge/gateway_runtime:dev")
        raise AdapterStartError(f"Unsupported sink type: {sink_type}")

    @staticmethod
    def _command_for(sink_type: str) -> list[str]:
        if sink_type in {"timescaledb", "sink-timescaledb", "sink_timescaledb"}:
            return ["python", "-m", "sinks.sink_timescaledb.main"]
        if sink_type in {"kafka", "sink-kafka", "sink_kafka"}:
            return ["python", "-m", "sinks.sink_kafka.main"]
        if sink_type in {"http", "sink-http", "sink_http"}:
            return ["python", "-m", "sinks.sink_http.main"]
        if sink_type in {"alert_router", "sink-alert-router", "sink_alert_router"}:
            return ["python", "-m", "sinks.sink_alert_router.main"]
        raise AdapterStartError(f"Unsupported sink type: {sink_type}")

    @staticmethod
    def _compose_labels(sink_type: str) -> Dict[str, str]:
        project = SinkManager._compose_project()
        service = "sink_timescaledb"
        if sink_type in {"kafka", "sink-kafka", "sink_kafka"}:
            service = "sink_kafka"
        elif sink_type in {"http", "sink-http", "sink_http"}:
            service = "sink_http"
        elif sink_type in {"alert_router", "sink-alert-router", "sink_alert_router"}:
            service = "sink_alert_router"
        return {
            "com.docker.compose.project": project,
            "com.docker.compose.service": service,
            "com.docker.compose.oneoff": "False",
        }

    @staticmethod
    def _compose_project() -> str:
        return os.getenv("COMPOSE_PROJECT_NAME") or os.getenv("DOCKER_COMPOSE_PROJECT") or "deploy"

    @staticmethod
    def _inject_shared_env(env: Dict[str, str], config: dict[str, object]) -> None:
        shared = {
            "SCHEMA_REGISTRY_URL": str(config.get("schema_registry_url") or os.getenv("SCHEMA_REGISTRY_URL", "")),
            "SCHEMA_CACHE_PATH": str(config.get("schema_cache_path") or os.getenv("SCHEMA_CACHE_PATH", "/data/schemas.cache.json")),
            "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        }
        env.update({key: value for key, value in shared.items() if value != ""})
