"""Adapter manager for starting and monitoring adapters."""

from __future__ import annotations

import json
import logging
import os
import socket
import urllib.error
import urllib.request
from typing import Dict, List

from gateway_runtime.adapter_factory import AdapterFactory
from gateway_runtime.config import AdapterConfig
from gateway_runtime.docker_types import DockerClientLike, DockerContainerLike
from gateway_runtime.errors import AdapterStartError

try:
    from docker import errors as docker_errors  # type: ignore
except ModuleNotFoundError:
    docker_errors = None


logger = logging.getLogger(__name__)


class AdapterManager:
    """
    Starts and monitors adapter containers.
    """

    def __init__(self, factory: AdapterFactory) -> None:
        """Initialize manager with adapter factory."""
        self._factory = factory
        self._containers: Dict[str, str] = {}
        self._container_names: Dict[str, str] = {}
        self._throttle_state: Dict[str, Dict[str, object]] = {}
        self._last_throttle_policy: Dict[str, object] = {
            "mode": "normal",
            "multiplier": 1.0,
            "reason": None,
            "updated_at": None,
        }
        self._client: DockerClientLike | None = None
        self._network: str | None = None

    def start_all(self, configs: List[AdapterConfig]) -> None:
        """Start all adapters defined in config."""
        client = self._docker_client()
        network = self._resolve_network(client)
        desired_ids = {config.adapter_id for config in configs}
        self._prune_orphaned_containers(client, desired_ids)

        for config in configs:
            if config.adapter_id in self._containers:
                raise AdapterStartError(f"Adapter already running: {config.adapter_id}")

            container_name = self._container_name(config.adapter_id)
            image = self._image_for(config.adapter_type)
            env = {
                "ADAPTER_CONFIG_JSON": json.dumps(config.config),
                "ADAPTER_CONFIG": json.dumps(config.config),
                "ADAPTER_ID": config.adapter_id,
                "ADAPTER_TYPE": config.adapter_type,
            }
            self._inject_shared_env(env, config.config)

            labels = self._labels_for(config.adapter_id, config.adapter_type)
            command = self._command_for(config.adapter_type)
            devices = self._device_mappings(config.config)

            container = self._ensure_container(
                client=client,
                name=container_name,
                image=image,
                environment=env,
                network=network,
                labels=labels,
                command=command,
                devices=devices,
            )

            self._containers[config.adapter_id] = container.id
            self._container_names[config.adapter_id] = container.name
            self._throttle_state[config.adapter_id] = self._default_throttle_state()
            logger.info("adapter manager started %s as %s", config.adapter_id, container.name)

    def stop_all(self) -> None:
        """Stop all running adapters."""
        client = self._docker_client()
        for adapter_id, container_id in list(self._containers.items()):
            self._stop_container(client, container_id)
            self._containers.pop(adapter_id, None)
            self._container_names.pop(adapter_id, None)
            self._throttle_state.pop(adapter_id, None)

    def start_adapter(self, config: AdapterConfig) -> None:
        """Start a single adapter with given config."""
        if config.adapter_id in self._containers:
            # Already running; stop it first to apply new config
            self.stop_adapter(config.adapter_id)
        
        client = self._docker_client()
        network = self._resolve_network(client)
        
        container_name = self._container_name(config.adapter_id)
        image = self._image_for(config.adapter_type)
        env = {
            "ADAPTER_CONFIG_JSON": json.dumps(config.config),
            "ADAPTER_CONFIG": json.dumps(config.config),
            "ADAPTER_ID": config.adapter_id,
            "ADAPTER_TYPE": config.adapter_type,
        }
        self._inject_shared_env(env, config.config)
        
        labels = self._labels_for(config.adapter_id, config.adapter_type)
        command = self._command_for(config.adapter_type)
        devices = self._device_mappings(config.config)
        
        container = self._ensure_container(
            client=client,
            name=container_name,
            image=image,
            environment=env,
            network=network,
            labels=labels,
            command=command,
            devices=devices,
        )
        
        self._containers[config.adapter_id] = container.id
        self._container_names[config.adapter_id] = container.name
        self._throttle_state[config.adapter_id] = self._default_throttle_state()
        logger.info("adapter manager started %s as %s", config.adapter_id, container.name)

    def stop_adapter(self, adapter_id: str) -> None:
        """Stop a single adapter by ID."""
        if adapter_id not in self._containers:
            return
        
        client = self._docker_client()
        container_id = self._containers[adapter_id]
        self._stop_container(client, container_id)
        self._containers.pop(adapter_id, None)
        self._container_names.pop(adapter_id, None)
        self._throttle_state.pop(adapter_id, None)
        logger.info("adapter manager stopped %s", adapter_id)

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
            container = self._get_container(client, container_id, context=f"reading health for adapter {adapter_id}")
            status = container.status if container is not None else "missing"

            adapter_states[adapter_id] = status

        overall = "healthy" if all(state == "running" for state in adapter_states.values()) else "degraded"

        return {
            "status": overall,
            "adapters": adapter_states,
            "throttle": {
                "policy": dict(self._last_throttle_policy),
                "adapters": {adapter_id: dict(state) for adapter_id, state in self._throttle_state.items()},
            },
        }

    def apply_throttle_policy(self, policy: Dict[str, object]) -> None:
        """Push the current runtime throttle policy to all running adapters."""
        self._last_throttle_policy = dict(policy)
        if not self._containers:
            return

        for adapter_id in list(self._containers):
            self._apply_throttle_to_adapter(adapter_id, policy)

    def _docker_client(self) -> DockerClientLike:
        """Create the optional Docker client lazily for adapter management."""
        if self._client is None:
            try:
                import docker  # type: ignore
            except ModuleNotFoundError as exc:
                raise AdapterStartError("docker SDK is required to manage adapters") from exc

            self._client = docker.from_env()
        return self._client

    def _resolve_network(self, client: DockerClientLike) -> str:
        """Infer the Docker network adapters should join in the current runtime."""
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
            logger.warning("adapter manager could not infer runtime docker network; falling back to bridge: %s", exc)

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
        devices: list[str],
    ) -> DockerContainerLike:
        """Replace any stale adapter container and start a fresh one."""
        container = self._get_container(client, name, context=f"checking for existing adapter container {name}")
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
            devices=devices,
            restart_policy={"Name": "unless-stopped"},
        )

    def _prune_orphaned_containers(self, client: DockerClientLike, desired_ids: set[str]) -> None:
        """Remove managed adapter containers that do not belong to the desired config set."""
        for container in self._list_managed_containers(client):
            adapter_id = self._managed_adapter_id(container)
            if adapter_id is None or adapter_id in desired_ids:
                continue
            logger.info(
                "adapter manager pruning orphaned managed container %s for adapter %s",
                getattr(container, "name", "<unknown>"),
                adapter_id,
            )
            self._stop_container(client, container.id)

    def _list_managed_containers(self, client: DockerClientLike) -> list[DockerContainerLike]:
        try:
            return list(client.containers.list(all=True))
        except Exception as exc:
            logger.warning("adapter manager failed to list managed containers: %s", exc)
            return []

    def _managed_adapter_id(self, container: DockerContainerLike) -> str | None:
        if not self._is_managed_container(container):
            return None
        labels = container.labels or {}
        adapter_id = labels.get("adapter_id")
        if isinstance(adapter_id, str) and adapter_id.strip():
            return adapter_id.strip()
        name = getattr(container, "name", "").lstrip("/")
        prefix = "sf-adapter-"
        if name.startswith(prefix):
            return name[len(prefix) :]
        return None

    def _is_managed_container(self, container: DockerContainerLike) -> bool:
        labels = container.labels or {}
        name = getattr(container, "name", "").lstrip("/")
        if labels.get("component") != "adapter":
            return False
        if labels.get("streamforge.managed-by") == "gateway_runtime":
            return self._matches_project(labels)
        if labels.get("app") == "streamforge":
            return self._matches_project(labels)
        return name.startswith("sf-adapter-")

    @staticmethod
    def _matches_project(labels: Dict[str, str]) -> bool:
        project = labels.get("com.docker.compose.project")
        if not project:
            return True
        return project == AdapterManager._compose_project()

    def _stop_container(self, client: DockerClientLike, container_id: str) -> None:
        container = self._get_container(client, container_id, context=f"stopping adapter container {container_id}")
        if container is None:
            return
        try:
            container.stop(timeout=5)
            container.remove()
        except Exception as exc:
            logger.warning("adapter manager failed to stop container %s cleanly: %s", container_id, exc)

    @staticmethod
    def _labels_for(adapter_id: str, adapter_type: str) -> Dict[str, str]:
        labels = {
            "app": "streamforge",
            "component": "adapter",
            "streamforge.managed-by": "gateway_runtime",
            "adapter_id": adapter_id,
            "adapter_type": adapter_type,
        }
        labels.update(AdapterManager._compose_labels(adapter_type))
        return labels

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
        """Resolve one adapter container while preserving not-found semantics."""
        try:
            return client.containers.get(container_ref)
        except Exception as exc:
            if self._is_docker_not_found(exc):
                return None
            logger.warning("adapter manager failed to resolve container %s while %s: %s", container_ref, context, exc)
            return None

    @staticmethod
    def _container_name(adapter_id: str) -> str:
        return f"sf-adapter-{adapter_id}"

    @staticmethod
    def _image_for(adapter_type: str) -> str:
        if adapter_type == "modbus_tcp":
            return os.getenv("ADAPTER_MODBUS_TCP_IMAGE", "streamforge/gateway_runtime:dev")
        if adapter_type == "modbus_rtu":
            return os.getenv("ADAPTER_MODBUS_RTU_IMAGE", "streamforge/gateway_runtime:dev")
        if adapter_type == "mqtt":
            return os.getenv("ADAPTER_MQTT_IMAGE", "streamforge/gateway_runtime:dev")
        if adapter_type == "opcua":
            return os.getenv("ADAPTER_OPCUA_IMAGE", "streamforge/gateway_runtime:dev")

        raise AdapterStartError(f"Unsupported adapter type: {adapter_type}")

    @staticmethod
    def _command_for(adapter_type: str) -> list[str]:
        if adapter_type == "modbus_tcp":
            return ["python", "-m", "adapters.adapter_modbus_tcp.main"]
        if adapter_type == "modbus_rtu":
            return ["python", "-m", "adapters.adapter_modbus_rtu.main"]
        if adapter_type == "mqtt":
            return ["python", "-m", "adapters.adapter_mqtt.main"]
        if adapter_type == "opcua":
            return ["python", "-m", "adapters.adapter_opcua.main"]

        raise AdapterStartError(f"Unsupported adapter type: {adapter_type}")

    @staticmethod
    def _compose_labels(adapter_type: str = "modbus_tcp") -> Dict[str, str]:
        project = AdapterManager._compose_project()
        service = "adapter_modbus_tcp"
        if adapter_type == "modbus_rtu":
            service = "adapter_modbus_rtu"
        elif adapter_type == "mqtt":
            service = "adapter_mqtt"
        elif adapter_type == "opcua":
            service = "adapter_opcua"
        return {
            "com.docker.compose.project": project,
            "com.docker.compose.service": service,
            "com.docker.compose.oneoff": "False",
        }

    @staticmethod
    def _compose_project() -> str:
        return os.getenv("COMPOSE_PROJECT_NAME") or os.getenv("DOCKER_COMPOSE_PROJECT") or "deploy"

    @staticmethod
    def _device_mappings(config: dict[str, object]) -> list[str]:
        devices: list[str] = []
        raw_devices = config.get("devices")
        if isinstance(raw_devices, list):
            for item in raw_devices:
                if isinstance(item, str) and item.strip():
                    devices.append(item.strip())
        serial_port = config.get("port") or config.get("device") or config.get("serial_port")
        if isinstance(serial_port, str) and serial_port.startswith("/dev/"):
            mapping = f"{serial_port}:{serial_port}:rwm"
            if mapping not in devices:
                devices.append(mapping)
        return devices

    @staticmethod
    def _inject_shared_env(env: Dict[str, str], config: dict[str, object]) -> None:
        output = config.get("output") if isinstance(config.get("output"), dict) else {}
        shared = {
            "SCHEMA_REGISTRY_URL": str(output.get("schema_registry_url") or os.getenv("SCHEMA_REGISTRY_URL", "")),
            "SCHEMA_CACHE_PATH": str(output.get("schema_cache_path") or os.getenv("SCHEMA_CACHE_PATH", "/data/schemas.cache.json")),
            "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
            "ADAPTER_HEALTH_PORT": os.getenv("ADAPTER_HEALTH_PORT", "8080"),
        }
        env.update({key: value for key, value in shared.items() if value != ""})

    def _apply_throttle_to_adapter(self, adapter_id: str, policy: Dict[str, object]) -> None:
        container_name = self._container_names.get(adapter_id) or self._container_name(adapter_id)
        payload = json.dumps(
            {
                "mode": str(policy.get("mode", "normal")),
                "multiplier": float(policy.get("multiplier", 1.0)),
                "reason": policy.get("reason"),
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self._throttle_url(container_name),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            logger.warning("adapter manager failed to push throttle policy to %s via %s: %s", adapter_id, container_name, exc)
            self._throttle_state[adapter_id] = {
                "status": "error",
                "error": str(exc),
                "updated_at": None,
            }
            return

        body["status"] = "ok"
        self._throttle_state[adapter_id] = body

    @staticmethod
    def _throttle_url(container_name: str) -> str:
        port = int(os.getenv("ADAPTER_HEALTH_PORT", "8080"))
        return f"http://{container_name}:{port}/control/throttle"

    @staticmethod
    def _default_throttle_state() -> Dict[str, object]:
        return {
            "status": "pending",
            "throttle_mode": "normal",
            "throttle_multiplier": 1.0,
            "effective_poll_interval_ms": None,
            "reason": None,
            "updated_at": None,
        }
