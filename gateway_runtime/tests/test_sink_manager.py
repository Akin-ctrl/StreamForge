"""Tests for sink container launch metadata."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from gateway_runtime.errors import AdapterStartError
from gateway_runtime.sink_manager import SinkManager


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


class SinkManagerMetadataTests(unittest.TestCase):
    def test_timescaledb_defaults_to_runtime_image_for_dev_stack(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(SinkManager._image_for("timescaledb"), "streamforge/gateway_runtime:dev")

    def test_kafka_defaults_to_runtime_image_for_dev_stack(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(SinkManager._image_for("kafka"), "streamforge/gateway_runtime:dev")

    def test_kafka_image_can_be_overridden(self) -> None:
        with patch.dict(os.environ, {"SINK_KAFKA_IMAGE": "streamforge/sink_kafka:dev"}, clear=False):
            self.assertEqual(SinkManager._image_for("kafka"), "streamforge/sink_kafka:dev")

    def test_http_defaults_to_runtime_image_for_dev_stack(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(SinkManager._image_for("http"), "streamforge/gateway_runtime:dev")

    def test_alert_router_defaults_to_runtime_image_for_dev_stack(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(SinkManager._image_for("alert_router"), "streamforge/gateway_runtime:dev")

    def test_kafka_launch_command_is_explicit(self) -> None:
        self.assertEqual(
            SinkManager._command_for("kafka"),
            ["python", "-m", "sinks.sink_kafka.main"],
        )

    def test_http_launch_command_is_explicit(self) -> None:
        self.assertEqual(
            SinkManager._command_for("http"),
            ["python", "-m", "sinks.sink_http.main"],
        )

    def test_alert_router_launch_command_is_explicit(self) -> None:
        self.assertEqual(
            SinkManager._command_for("alert_router"),
            ["python", "-m", "sinks.sink_alert_router.main"],
        )

    def test_kafka_compose_service_label_matches_sink(self) -> None:
        labels = SinkManager._compose_labels("kafka")
        self.assertEqual(labels["com.docker.compose.service"], "sink_kafka")

    def test_http_compose_service_label_matches_sink(self) -> None:
        labels = SinkManager._compose_labels("http")
        self.assertEqual(labels["com.docker.compose.service"], "sink_http")

    def test_alert_router_compose_service_label_matches_sink(self) -> None:
        labels = SinkManager._compose_labels("alert_router")
        self.assertEqual(labels["com.docker.compose.service"], "sink_alert_router")

    def test_unsupported_sink_type_raises(self) -> None:
        with self.assertRaises(AdapterStartError):
            SinkManager._command_for("unsupported")

    def test_prune_orphaned_containers_removes_unconfigured_streamforge_sink(self) -> None:
        manager = SinkManager()
        client = FakeDockerClient(
            [
                FakeManagedContainer(
                    "sf-sink-orphaned",
                    {
                        "app": "streamforge",
                        "component": "sink",
                        "sink_id": "orphaned",
                        "com.docker.compose.project": "deploy",
                    },
                ),
                FakeManagedContainer(
                    "sf-sink-keep",
                    {
                        "app": "streamforge",
                        "component": "sink",
                        "sink_id": "keep",
                        "com.docker.compose.project": "deploy",
                    },
                ),
            ]
        )

        with patch.object(manager, "_stop_container") as stop_mock:
            manager._prune_orphaned_containers(client, {"keep"})

        self.assertEqual(stop_mock.call_count, 1)
        self.assertEqual(stop_mock.call_args.args[1], "sf-sink-orphaned")


if __name__ == "__main__":
    unittest.main()
