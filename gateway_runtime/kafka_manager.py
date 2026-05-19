"""Kafka manager for local embedded Kafka (KRaft)."""

from __future__ import annotations

import logging
import os
import socket
import time
from typing import Dict

from gateway_runtime.docker_types import DockerClientLike, DockerContainerLike
from gateway_runtime.errors import KafkaError


logger = logging.getLogger(__name__)


def _docker_error_types() -> tuple[type[BaseException], ...]:
    """Return the docker-side exceptions expected during Kafka management."""
    error_types: list[type[BaseException]] = [RuntimeError, OSError]
    try:
        from docker.errors import APIError, DockerException, NotFound  # type: ignore
    except ModuleNotFoundError:
        return tuple(error_types)
    return tuple(error_types + [NotFound, APIError, DockerException])


def _container_lookup_error_types() -> tuple[type[BaseException], ...]:
    return _docker_error_types() + (KafkaError,)


class KafkaManager:
    """
    Manages local Kafka lifecycle (embedded single-node KRaft).
    """

    def __init__(self, bootstrap: str) -> None:
        """Initialize with local Kafka bootstrap address."""
        self._bootstrap = bootstrap
        self._host, self._port = self._parse_bootstrap(bootstrap)
        self._auto_manage = os.getenv("KAFKA_AUTO_MANAGE", "true").lower() in {"1", "true", "yes", "on"}
        self._start_timeout_s = int(os.getenv("KAFKA_START_TIMEOUT", "60"))
        self._image = os.getenv("KAFKA_IMAGE", "confluentinc/cp-kafka:7.5.0")
        self._cluster_id = os.getenv("KAFKA_CLUSTER_ID", "MkU3OEVBNTcwNTJENDM2Qk")
        self._container_name = os.getenv("KAFKA_CONTAINER_NAME", self._default_container_name())
        self._container_network_mode = os.getenv("KAFKA_CONTAINER_NETWORK_MODE", self._default_network_mode())
        self._host_data_dir = os.getenv("KAFKA_DATA_DIR")
        self._data_volume = os.getenv("KAFKA_DATA_VOLUME", f"{self._container_name}-data")
        self._client: DockerClientLike | None = None
        self._network: str | None = None
        self._managed_container_id: str | None = None
        self._managed_by_runtime = False

    def start(self) -> None:
        """Start local Kafka (container or process)."""
        if self._can_connect():
            self._adopt_existing_container()
            return

        if not self._auto_manage:
            raise KafkaError(f"Kafka not reachable at {self._bootstrap}")

        self._ensure_running()

    def stop(self) -> None:
        """Stop local Kafka."""
        if not self._managed_by_runtime or not self._managed_container_id:
            return None

        client = self._docker_client()
        self._stop_container(client, self._managed_container_id)
        self._managed_container_id = None
        self._managed_by_runtime = False
        return None

    def health(self) -> Dict[str, object]:
        """Return Kafka health status."""
        reachable = self._can_connect()
        container_status = self._container_status()
        return {
            "status": "healthy" if reachable else "failed",
            "bootstrap": self._bootstrap,
            "reachable": reachable,
            "managed": self._managed_by_runtime,
            "management_mode": "runtime" if self._managed_by_runtime else ("auto-external" if self._auto_manage else "external"),
            "container_name": self._container_name if self._auto_manage else None,
            "container_status": container_status,
        }

    @property
    def bootstrap(self) -> str:
        """Return bootstrap server address."""
        return self._bootstrap

    @property
    def container_name(self) -> str:
        """Return the managed/external Kafka container name."""
        return self._container_name

    def ensure_running(self) -> None:
        """Ensure Kafka remains available during runtime supervision."""
        if self._can_connect():
            return

        if not self._auto_manage:
            raise KafkaError(f"Kafka became unavailable at {self._bootstrap}")

        self._ensure_running()

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

    def _ensure_running(self) -> None:
        client = self._docker_client()
        network = None if self._uses_host_network() else self._resolve_network(client)
        container = self._ensure_container(client=client, network=network)

        self._managed_container_id = container.id
        if self._wait_for_port(timeout_s=self._start_timeout_s):
            return

        raise KafkaError(f"Managed Kafka did not become reachable at {self._bootstrap}")

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

    def _docker_client(self) -> DockerClientLike:
        """Create the optional Docker client lazily for runtime-managed Kafka."""
        if self._client is None:
            try:
                import docker  # type: ignore
            except ModuleNotFoundError as exc:
                raise KafkaError("docker SDK is required to manage embedded Kafka") from exc

            self._client = docker.from_env()
        return self._client

    def _adopt_existing_container(self) -> None:
        if not self._auto_manage:
            return

        try:
            container = self._find_container(self._docker_client(), self._container_name)
        except _container_lookup_error_types():
            return

        self._container_name = container.name
        self._managed_container_id = container.id
        self._managed_by_runtime = self._is_runtime_managed(container)

    def _resolve_network(self, client: DockerClientLike) -> str:
        """Infer the Docker network that runtime-managed Kafka should join."""
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
        except _docker_error_types():
            logger.debug("falling back to bridge network for embedded Kafka discovery")

        self._network = "bridge"
        return self._network

    def _ensure_container(self, client: DockerClientLike, network: str | None) -> DockerContainerLike:
        """Reuse or create the Kafka container that backs the embedded broker."""
        try:
            container = self._find_container(client, self._container_name)
            self._container_name = container.name
            self._managed_by_runtime = self._is_runtime_managed(container)
            if container.status != "running":
                container.start()
            return container
        except _container_lookup_error_types():
            labels = {
                "app": "streamforge",
                "component": "kafka",
                "streamforge.managed-by": "gateway_runtime",
            }
            self._managed_by_runtime = True
            run_kwargs = {
                "image": self._image,
                "name": self._container_name,
                "detach": True,
                "environment": self._kafka_environment(),
                "labels": labels,
                "restart_policy": {"Name": "unless-stopped"},
                "hostname": self._broker_host(),
                "volumes": self._volume_spec(),
            }

            if self._uses_host_network():
                run_kwargs["network_mode"] = self._container_network_mode
            else:
                run_kwargs["network"] = network

            return client.containers.run(**run_kwargs)

    @staticmethod
    def _stop_container(client: DockerClientLike, container_id: str) -> None:
        try:
            container = client.containers.get(container_id)
            container.stop(timeout=10)
            container.remove()
        except _docker_error_types():
            return None

    @staticmethod
    def _is_runtime_managed(container: DockerContainerLike) -> bool:
        labels = container.labels or {}
        return labels.get("streamforge.managed-by") == "gateway_runtime" and labels.get("component") == "kafka"

    def _container_status(self) -> str | None:
        if not self._auto_manage:
            return None
        if not self._managed_by_runtime and not self._managed_container_id:
            return "untracked"

        target = self._managed_container_id or self._container_name
        try:
            container = self._find_container(self._docker_client(), target)
            return container.status
        except _container_lookup_error_types():
            return "missing"

    def _find_container(self, client: DockerClientLike, target: str) -> DockerContainerLike:
        """Resolve a Kafka container by ID, name, or compose-derived alias."""
        try:
            return client.containers.get(target)
        except _docker_error_types():
            pass

        for container in client.containers.list(all=True):
            if self._matches_container(container, target):
                return container

        raise KafkaError(f"Kafka container {target} not found")

    @staticmethod
    def _matches_container(container: DockerContainerLike, target: str) -> bool:
        if container.name == target:
            return True

        labels = container.labels or {}
        if labels.get("com.docker.compose.service") == target:
            return True

        config = container.attrs.get("Config", {})
        if config.get("Hostname") == target:
            return True

        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        for network in networks.values():
            aliases = network.get("Aliases") or []
            if target in aliases:
                return True

        return False

    def _kafka_environment(self) -> Dict[str, str]:
        broker_host = self._broker_host()
        return {
            "CLUSTER_ID": self._cluster_id,
            "KAFKA_NODE_ID": "1",
            "KAFKA_PROCESS_ROLES": "broker,controller",
            "KAFKA_CONTROLLER_QUORUM_VOTERS": f"1@{broker_host}:9093",
            "KAFKA_LISTENERS": f"PLAINTEXT://0.0.0.0:{self._port},CONTROLLER://0.0.0.0:9093",
            "KAFKA_ADVERTISED_LISTENERS": f"PLAINTEXT://{broker_host}:{self._port}",
            "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP": "PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT",
            "KAFKA_CONTROLLER_LISTENER_NAMES": "CONTROLLER",
            "KAFKA_LOG_DIRS": "/var/lib/kafka/data",
            "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": "1",
            "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR": "1",
            "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR": "1",
            "KAFKA_AUTO_CREATE_TOPICS_ENABLE": os.getenv("KAFKA_AUTO_CREATE_TOPICS_ENABLE", "true"),
        }

    def _volume_spec(self) -> Dict[str, Dict[str, str]]:
        if self._host_data_dir:
            os.makedirs(self._host_data_dir, exist_ok=True)
            return {
                self._host_data_dir: {"bind": "/var/lib/kafka/data", "mode": "rw"},
            }

        return {
            self._data_volume: {"bind": "/var/lib/kafka/data", "mode": "rw"},
        }

    def _default_container_name(self) -> str:
        if self._host and self._host not in {"127.0.0.1", "localhost"}:
            return self._host
        return "sf-kafka"

    def _default_network_mode(self) -> str:
        if self._host in {"127.0.0.1", "localhost"}:
            return "host"
        return ""

    def _uses_host_network(self) -> bool:
        return bool(self._container_network_mode)

    def _broker_host(self) -> str:
        if self._uses_host_network() and self._host in {"localhost", "127.0.0.1"}:
            return "127.0.0.1"
        return self._host
