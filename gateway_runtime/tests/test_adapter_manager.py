"""Tests for adapter container launch metadata."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from gateway_runtime.adapter_manager import AdapterManager
from gateway_runtime.adapter_factory import AdapterFactory
from gateway_runtime.config import AdapterConfig
from gateway_runtime.errors import AdapterStartError


class FakeManagedContainer:
    def __init__(self, name: str, labels: dict[str, str], container_id: str | None = None) -> None:
        self.name = name
        self.labels = labels
        self.id = container_id or name


class FakeContainerCollection:
    def __init__(self, containers: list[FakeManagedContainer]) -> None:
        self._containers = containers

    def list(self, all: bool = False):  # noqa: FBT002
        return list(self._containers)


class FakeDockerClient:
    def __init__(self, containers: list[FakeManagedContainer]) -> None:
        self.containers = FakeContainerCollection(containers)


class AdapterManagerMetadataTests(unittest.TestCase):
    def test_modbus_tcp_defaults_to_runtime_image_for_dev_stack(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(AdapterManager._image_for("modbus_tcp"), "streamforge/gateway_runtime:dev")

    def test_modbus_rtu_defaults_to_runtime_image_for_dev_stack(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(AdapterManager._image_for("modbus_rtu"), "streamforge/gateway_runtime:dev")

    def test_modbus_tcp_image_can_be_overridden(self) -> None:
        with patch.dict(os.environ, {"ADAPTER_MODBUS_TCP_IMAGE": "streamforge/adapter_modbus_tcp:dev"}, clear=False):
            self.assertEqual(AdapterManager._image_for("modbus_tcp"), "streamforge/adapter_modbus_tcp:dev")

    def test_modbus_rtu_image_can_be_overridden(self) -> None:
        with patch.dict(os.environ, {"ADAPTER_MODBUS_RTU_IMAGE": "streamforge/adapter_modbus_rtu:dev"}, clear=False):
            self.assertEqual(AdapterManager._image_for("modbus_rtu"), "streamforge/adapter_modbus_rtu:dev")

    def test_modbus_tcp_launch_command_is_explicit(self) -> None:
        self.assertEqual(
            AdapterManager._command_for("modbus_tcp"),
            ["python", "-m", "adapters.adapter_modbus_tcp.main"],
        )

    def test_modbus_rtu_launch_command_is_explicit(self) -> None:
        self.assertEqual(
            AdapterManager._command_for("modbus_rtu"),
            ["python", "-m", "adapters.adapter_modbus_rtu.main"],
        )

    def test_modbus_rtu_compose_service_label_matches_adapter(self) -> None:
        labels = AdapterManager._compose_labels("modbus_rtu")
        self.assertEqual(labels["com.docker.compose.service"], "adapter_modbus_rtu")

    def test_mqtt_defaults_to_runtime_image_for_dev_stack(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(AdapterManager._image_for("mqtt"), "streamforge/gateway_runtime:dev")

    def test_mqtt_image_can_be_overridden(self) -> None:
        with patch.dict(os.environ, {"ADAPTER_MQTT_IMAGE": "streamforge/adapter_mqtt:dev"}, clear=False):
            self.assertEqual(AdapterManager._image_for("mqtt"), "streamforge/adapter_mqtt:dev")

    def test_mqtt_launch_command_is_explicit(self) -> None:
        self.assertEqual(
            AdapterManager._command_for("mqtt"),
            ["python", "-m", "adapters.adapter_mqtt.main"],
        )

    def test_mqtt_compose_service_label_matches_adapter(self) -> None:
        labels = AdapterManager._compose_labels("mqtt")
        self.assertEqual(labels["com.docker.compose.service"], "adapter_mqtt")

    def test_opcua_defaults_to_runtime_image_for_dev_stack(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(AdapterManager._image_for("opcua"), "streamforge/gateway_runtime:dev")

    def test_opcua_image_can_be_overridden(self) -> None:
        with patch.dict(os.environ, {"ADAPTER_OPCUA_IMAGE": "streamforge/adapter_opcua:dev"}, clear=False):
            self.assertEqual(AdapterManager._image_for("opcua"), "streamforge/adapter_opcua:dev")

    def test_opcua_launch_command_is_explicit(self) -> None:
        self.assertEqual(
            AdapterManager._command_for("opcua"),
            ["python", "-m", "adapters.adapter_opcua.main"],
        )

    def test_opcua_compose_service_label_matches_adapter(self) -> None:
        labels = AdapterManager._compose_labels("opcua")
        self.assertEqual(labels["com.docker.compose.service"], "adapter_opcua")

    def test_device_mappings_include_serial_port_and_explicit_devices(self) -> None:
        mappings = AdapterManager._device_mappings(
            {
                "serial_port": "/dev/ttyUSB0",
                "devices": ["/dev/ttyS0:/dev/ttyS0:rwm"],
            }
        )
        self.assertEqual(
            mappings,
            [
                "/dev/ttyS0:/dev/ttyS0:rwm",
                "/dev/ttyUSB0:/dev/ttyUSB0:rwm",
            ],
        )

    def test_unsupported_adapter_type_raises(self) -> None:
        with self.assertRaises(AdapterStartError):
            AdapterManager._command_for("unsupported")

    def test_apply_throttle_policy_posts_to_running_adapter(self) -> None:
        manager = AdapterManager(AdapterFactory())
        manager._containers["modbus-demo-01"] = "container-id"
        manager._container_names["modbus-demo-01"] = "sf-adapter-modbus-demo-01"

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "adapter_id": "modbus-demo-01",
                        "throttle_mode": "high",
                        "throttle_multiplier": 5.0,
                        "effective_poll_interval_ms": 5000,
                        "reason": "validator_backpressure",
                    }
                ).encode("utf-8")

        with patch("gateway_runtime.adapter_manager.urllib.request.urlopen", return_value=FakeResponse()) as urlopen_mock:
            manager.apply_throttle_policy({"mode": "high", "multiplier": 5.0, "reason": "validator_backpressure"})

        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.full_url, "http://sf-adapter-modbus-demo-01:8080/control/throttle")
        self.assertEqual(manager._last_throttle_policy["mode"], "high")
        self.assertEqual(manager._throttle_state["modbus-demo-01"]["throttle_mode"], "high")

    def test_start_adapter_uses_managed_runtime_label(self) -> None:
        manager = AdapterManager(AdapterFactory())
        captured: dict[str, object] = {}
        config = AdapterConfig(
            adapter_id="modbus-demo-01",
            adapter_type="modbus_tcp",
            config={"host": "10.0.0.5", "port": 502, "output": {"topic": "telemetry.raw"}},
        )

        def fake_ensure_container(**kwargs):
            captured.update(kwargs)
            return FakeManagedContainer(
                name="sf-adapter-modbus-demo-01",
                labels=kwargs["labels"],
                container_id="container-1",
            )

        with (
            patch.object(manager, "_docker_client", return_value=object()),
            patch.object(manager, "_resolve_network", return_value="deploy_default"),
            patch.object(manager, "_ensure_container", side_effect=fake_ensure_container),
        ):
            manager.start_adapter(config)

        labels = captured["labels"]
        self.assertEqual(labels["streamforge.managed-by"], "gateway_runtime")
        self.assertEqual(labels["adapter_id"], "modbus-demo-01")
        self.assertEqual(manager._containers["modbus-demo-01"], "container-1")
        self.assertEqual(manager._container_names["modbus-demo-01"], "sf-adapter-modbus-demo-01")

    def test_prune_orphaned_containers_removes_unconfigured_streamforge_adapter(self) -> None:
        manager = AdapterManager(AdapterFactory())
        client = FakeDockerClient(
            [
                FakeManagedContainer(
                    "sf-adapter-orphaned",
                    {
                        "app": "streamforge",
                        "component": "adapter",
                        "adapter_id": "orphaned",
                        "com.docker.compose.project": "deploy",
                    },
                ),
                FakeManagedContainer(
                    "sf-adapter-keep",
                    {
                        "app": "streamforge",
                        "component": "adapter",
                        "adapter_id": "keep",
                        "com.docker.compose.project": "deploy",
                    },
                ),
            ]
        )

        with patch.object(manager, "_stop_container") as stop_mock:
            manager._prune_orphaned_containers(client, {"keep"})

        self.assertEqual(stop_mock.call_count, 1)
        self.assertEqual(stop_mock.call_args.args[1], "sf-adapter-orphaned")


if __name__ == "__main__":
    unittest.main()
