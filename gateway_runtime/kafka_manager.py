"""Manager for the local Kafka-compatible edge broker."""

from __future__ import annotations

import logging
import os
import socket
import time
from typing import Dict

from gateway_runtime.docker_types import DockerClientLike, DockerContainerLike
from gateway_runtime.errors import KafkaError


logger = logging.getLogger(__name__)

DEFAULT_CONFLUENT_IMAGE = "confluentinc/cp-kafka:7.5.0"
DEFAULT_REDPANDA_IMAGE = "redpandadata/redpanda:v26.1.9"
CONFLUENT_DATA_DIR = "/var/lib/kafka/data"
REDPANDA_DATA_DIR = "/var/lib/redpanda/data"
SUPPORTED_BROKER_FLAVORS = {"confluent", "redpanda"}


def _docker_error_types() -> tuple[type[BaseException], ...]:
    """Return the docker-side exceptions expected during broker management."""
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
    Manages the local Kafka-compatible broker lifecycle.

    Redpanda is the default embedded broker because it keeps Kafka protocol
    compatibility while reducing the edge footprint. The Confluent KRaft path
    remains available through ``KAFKA_BROKER_FLAVOR=confluent`` for compatibility.
    """

    def __init__(self, bootstrap: str) -> None:
        """Initialize with local broker bootstrap address."""
        self._bootstrap = bootstrap
        self._host, self._port = self._parse_bootstrap(bootstrap)
        self._auto_manage = os.getenv("KAFKA_AUTO_MANAGE", "true").lower() in {"1", "true", "yes", "on"}
        self._start_timeout_s = int(os.getenv("KAFKA_START_TIMEOUT", "60"))
        self._broker_flavor = os.getenv("KAFKA_BROKER_FLAVOR", "redpanda").strip().lower()
        if self._broker_flavor not in SUPPORTED_BROKER_FLAVORS:
            supported = ", ".join(sorted(SUPPORTED_BROKER_FLAVORS))
            raise KafkaError(f"Unsupported broker flavor {self._broker_flavor!r}; expected one of: {supported}")
        self._image = self._configured_image()
        self._cluster_id = os.getenv("KAFKA_CLUSTER_ID", "MkU3OEVBNTcwNTJENDM2Qk")
        self._container_name = os.getenv("KAFKA_CONTAINER_NAME", self._default_container_name())
        self._container_network_mode = os.getenv("KAFKA_CONTAINER_NETWORK_MODE", self._default_network_mode())
        self._host_data_dir = os.getenv("REDPANDA_DATA_DIR") or os.getenv("KAFKA_DATA_DIR")
        self._data_volume = os.getenv("REDPANDA_DATA_VOLUME") or os.getenv("KAFKA_DATA_VOLUME") or self._default_data_volume()
        self._redpanda_rpc_port = int(os.getenv("REDPANDA_RPC_PORT", "33145"))
        self._redpanda_schema_registry_port = int(os.getenv("REDPANDA_SCHEMA_REGISTRY_PORT", "8081"))
        self._redpanda_smp = os.getenv("REDPANDA_SMP", "1")
        self._client: DockerClientLike | None = None
        self._network: str | None = None
        self._managed_container_id: str | None = None
        self._managed_by_runtime = False

    def start(self) -> None:
        """Start the local broker container when the endpoint is not reachable."""
        if self._can_connect():
            self._adopt_existing_container()
            return

        if not self._auto_manage:
            raise KafkaError(f"Broker not reachable at {self._bootstrap}")

        self._ensure_running()

    def stop(self) -> None:
        """Stop the runtime-managed local broker."""
        if not self._managed_by_runtime or not self._managed_container_id:
            return None

        client = self._docker_client()
        self._stop_container(client, self._managed_container_id)
        self._managed_container_id = None
        self._managed_by_runtime = False
        return None

    def health(self) -> Dict[str, object]:
        """Return local broker health status."""
        reachable = self._can_connect()
        container_status = self._container_status()
        return {
            "status": "healthy" if reachable else "failed",
            "bootstrap": self._bootstrap,
            "broker_flavor": self._broker_flavor,
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
        """Return the managed/external broker container name."""
        return self._container_name

    def ensure_running(self) -> None:
        """Ensure the broker remains available during runtime supervision."""
        if self._can_connect():
            return

        if not self._auto_manage:
            raise KafkaError(f"Broker became unavailable at {self._bootstrap}")

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

        raise KafkaError(f"Managed broker did not become reachable at {self._bootstrap}")

    def _wait_for_port(self, timeout_s: int) -> bool:
        """Check if the broker port is reachable within timeout."""
        end_time = time.time() + timeout_s
        while time.time() < end_time:
            if self._can_connect():
                return True
            time.sleep(0.2)
        return False

    def _can_connect(self) -> bool:
        """Attempt a TCP connection to the broker host:port."""
        try:
            with socket.create_connection((self._host, self._port), timeout=1):
                return True
        except OSError:
            return False

    def _docker_client(self) -> DockerClientLike:
        """Create the optional Docker client lazily for runtime-managed brokers."""
        if self._client is None:
            try:
                import docker  # type: ignore
            except ModuleNotFoundError as exc:
                raise KafkaError("docker SDK is required to manage the embedded broker") from exc

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
        """Infer the Docker network that the runtime-managed broker should join."""
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
            logger.debug("falling back to bridge network for embedded broker discovery")

        self._network = "bridge"
        return self._network

    def _ensure_container(self, client: DockerClientLike, network: str | None) -> DockerContainerLike:
        """Reuse or create the container that backs the embedded broker."""
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
                "environment": self._container_environment(),
                "labels": labels,
                "restart_policy": {"Name": "unless-stopped"},
                "hostname": self._broker_host(),
                "volumes": self._volume_spec(),
            }
            command = self._container_command()
            if command is not None:
                run_kwargs["command"] = command

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
        """Resolve a broker container by ID, name, or compose-derived alias."""
        try:
            return client.containers.get(target)
        except _docker_error_types():
            pass

        for container in client.containers.list(all=True):
            if self._matches_container(container, target):
                return container

        raise KafkaError(f"Broker container {target} not found")

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

    def _container_environment(self) -> Dict[str, str]:
        if self._is_redpanda():
            return {}

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
            "KAFKA_LOG_DIRS": CONFLUENT_DATA_DIR,
            "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": "1",
            "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR": "1",
            "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR": "1",
            "KAFKA_AUTO_CREATE_TOPICS_ENABLE": os.getenv("KAFKA_AUTO_CREATE_TOPICS_ENABLE", "true"),
        }

    def _container_command(self) -> list[str] | None:
        if not self._is_redpanda():
            return None

        broker_host = self._broker_host()
        return [
            "redpanda",
            "start",
            "--kafka-addr",
            f"internal://0.0.0.0:{self._port}",
            "--advertise-kafka-addr",
            f"internal://{broker_host}:{self._port}",
            "--schema-registry-addr",
            f"internal://0.0.0.0:{self._redpanda_schema_registry_port}",
            "--rpc-addr",
            f"{broker_host}:{self._redpanda_rpc_port}",
            "--advertise-rpc-addr",
            f"{broker_host}:{self._redpanda_rpc_port}",
            "--mode",
            "dev-container",
            "--smp",
            self._redpanda_smp,
            "--default-log-level=info",
        ]

    def _volume_spec(self) -> Dict[str, Dict[str, str]]:
        container_data_dir = self._container_data_dir()
        if self._host_data_dir:
            os.makedirs(self._host_data_dir, exist_ok=True)
            return {
                self._host_data_dir: {"bind": container_data_dir, "mode": "rw"},
            }

        return {
            self._data_volume: {"bind": container_data_dir, "mode": "rw"},
        }

    def _default_container_name(self) -> str:
        if self._host and self._host not in {"127.0.0.1", "localhost"}:
            return self._host
        if self._is_redpanda():
            return "sf-redpanda"
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

    def _configured_image(self) -> str:
        if self._is_redpanda():
            return os.getenv("REDPANDA_IMAGE") or os.getenv("KAFKA_IMAGE", DEFAULT_REDPANDA_IMAGE)
        return os.getenv("KAFKA_IMAGE", DEFAULT_CONFLUENT_IMAGE)

    def _default_data_volume(self) -> str:
        if self._is_redpanda():
            return f"{self._container_name}-redpanda-data"
        return f"{self._container_name}-data"

    def _container_data_dir(self) -> str:
        if self._is_redpanda():
            return REDPANDA_DATA_DIR
        return CONFLUENT_DATA_DIR

    def _is_redpanda(self) -> bool:
        return self._broker_flavor == "redpanda"
