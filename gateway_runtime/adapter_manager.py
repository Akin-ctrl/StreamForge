"""Adapter manager for starting and monitoring adapters."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Dict, List

from gateway_runtime.adapter_factory import AdapterFactory
from gateway_runtime.config import AdapterConfig
from gateway_runtime.errors import AdapterStartError


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
                "ADAPTER_ID": config.adapter_id,
                "ADAPTER_TYPE": config.adapter_type,
            }
            self._inject_shared_env(env, config.config)

            labels = {
                "app": "streamforge",
                "component": "adapter",
                "adapter_id": config.adapter_id,
                "adapter_type": config.adapter_type,
            }
            labels.update(self._compose_labels())
            command = self._command_for(config.adapter_type)

            container = self._ensure_container(
                client=client,
                name=container_name,
                image=image,
                environment=env,
                network=network,
                labels=labels,
                command=command,
            )

            self._containers[config.adapter_id] = container.id
            self._container_names[config.adapter_id] = container.name
            self._throttle_state[config.adapter_id] = self._default_throttle_state()
            print(f"adapter_manager started {config.adapter_id} as {container.name}", flush=True)

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
        
        labels = {
            "app": "streamforge",
            "component": "adapter",
            "adapter_id": config.adapter_id,
            "adapter_type": config.adapter_type,
        }
        labels.update(self._compose_labels())
        command = self._command_for(config.adapter_type)
        
        container = self._ensure_container(
            client=client,
            name=container_name,
            image=image,
            environment=env,
            network=network,
            labels=labels,
            command=command,
        )
        
        self._containers[config.adapter_id] = container.id
        self._container_names[config.adapter_id] = container.name
        self._throttle_state[config.adapter_id] = self._default_throttle_state()
        print(f"adapter_manager started {config.adapter_id} as {container.name}", flush=True)

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
        print(f"adapter_manager stopped {adapter_id}", flush=True)

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
        command: list[str],
    ):
        try:
            container = client.containers.get(name)
            self._stop_container(client, container.id)
        except Exception:
            pass

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
            return os.getenv("ADAPTER_MODBUS_TCP_IMAGE", "streamforge/gateway_runtime:dev")

        raise AdapterStartError(f"Unsupported adapter type: {adapter_type}")

    @staticmethod
    def _command_for(adapter_type: str) -> list[str]:
        if adapter_type == "modbus_tcp":
            return ["python", "-m", "adapters.adapter_modbus_tcp.main"]

        raise AdapterStartError(f"Unsupported adapter type: {adapter_type}")

    @staticmethod
    def _compose_labels() -> Dict[str, str]:
        project = os.getenv("COMPOSE_PROJECT_NAME") or os.getenv("DOCKER_COMPOSE_PROJECT") or "deploy"
        return {
            "com.docker.compose.project": project,
            "com.docker.compose.service": "adapter_modbus_tcp",
            "com.docker.compose.oneoff": "False",
        }

    @staticmethod
    def _inject_shared_env(env: Dict[str, str], config: dict) -> None:
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
