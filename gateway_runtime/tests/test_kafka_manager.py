"""Tests for Kafka container discovery helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from gateway_runtime.errors import KafkaError
from gateway_runtime.kafka_manager import KafkaManager


class FakeContainer:
    def __init__(
        self,
        name: str,
        *,
        container_id: str = "container-1",
        labels: dict[str, str] | None = None,
        hostname: str | None = None,
        aliases: list[str] | None = None,
        status: str = "running",
    ) -> None:
        self.name = name
        self.id = container_id
        self.status = status
        self.labels = labels or {}
        self.attrs = {
            "Config": {"Hostname": hostname or name},
            "NetworkSettings": {"Networks": {"default": {"Aliases": aliases or []}}},
        }


class FakeContainers:
    def __init__(self, containers: list[FakeContainer]) -> None:
        self._containers = containers
        self.last_run_kwargs: dict[str, object] | None = None

    def get(self, target: str):
        for container in self._containers:
            if container.name == target or container.id == target:
                return container
        raise RuntimeError("not found")

    def list(self, all: bool = False):  # noqa: ARG002 - docker-compatible signature
        return list(self._containers)

    def run(self, **kwargs: object) -> FakeContainer:
        self.last_run_kwargs = kwargs
        container = FakeContainer(
            name=str(kwargs["name"]),
            container_id="created-container",
            labels=kwargs.get("labels") if isinstance(kwargs.get("labels"), dict) else None,
            hostname=str(kwargs["hostname"]),
        )
        self._containers.append(container)
        return container


class FakeDockerClient:
    def __init__(self, containers: list[FakeContainer]) -> None:
        self.containers = FakeContainers(containers)


class KafkaManagerContainerDiscoveryTests(unittest.TestCase):
    def test_adopts_compose_service_container_when_name_differs(self) -> None:
        manager = KafkaManager("kafka:9092")
        manager._client = FakeDockerClient(
            [
                FakeContainer(
                    name="deploy-kafka-1",
                    container_id="abc123",
                    labels={"com.docker.compose.service": "kafka"},
                    hostname="deploy-kafka-1",
                    aliases=["kafka"],
                )
            ]
        )

        manager._adopt_existing_container()

        self.assertEqual(manager.container_name, "deploy-kafka-1")
        self.assertEqual(manager._managed_container_id, "abc123")
        self.assertFalse(manager._managed_by_runtime)

    def test_matches_network_alias_when_service_label_missing(self) -> None:
        container = FakeContainer(
            name="broker-prod-1",
            hostname="broker-prod-1",
            aliases=["kafka", "broker"],
        )

        self.assertTrue(KafkaManager._matches_container(container, "kafka"))


class KafkaManagerBrokerConfigTests(unittest.TestCase):
    def test_redpanda_is_default_embedded_broker(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            manager = KafkaManager("kafka:9092")

        self.assertEqual(manager._broker_flavor, "redpanda")
        self.assertEqual(manager._image, "redpandadata/redpanda:v26.1.9")
        self.assertEqual(manager._container_environment(), {})
        self.assertEqual(
            manager._volume_spec(),
            {"kafka-redpanda-data": {"bind": "/var/lib/redpanda/data", "mode": "rw"}},
        )

        command = manager._container_command()
        self.assertIsNotNone(command)
        self.assertIn("--mode", command or [])
        self.assertIn("dev-container", command or [])
        self.assertIn("internal://kafka:9092", command or [])

    def test_confluent_flavor_keeps_legacy_kraft_configuration(self) -> None:
        with patch.dict("os.environ", {"KAFKA_BROKER_FLAVOR": "confluent"}, clear=True):
            manager = KafkaManager("kafka:9092")

        self.assertEqual(manager._image, "confluentinc/cp-kafka:7.5.0")
        self.assertIsNone(manager._container_command())
        self.assertEqual(
            manager._volume_spec(),
            {"kafka-data": {"bind": "/var/lib/kafka/data", "mode": "rw"}},
        )

        environment = manager._container_environment()
        self.assertEqual(environment["KAFKA_PROCESS_ROLES"], "broker,controller")
        self.assertEqual(environment["KAFKA_ADVERTISED_LISTENERS"], "PLAINTEXT://kafka:9092")

    def test_rejects_unknown_broker_flavor(self) -> None:
        with patch.dict("os.environ", {"KAFKA_BROKER_FLAVOR": "rabbitmq"}, clear=True):
            with self.assertRaises(KafkaError):
                KafkaManager("kafka:9092")

    def test_redpanda_container_run_uses_command_not_kafka_env(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            manager = KafkaManager("kafka:9092")
        client = FakeDockerClient([])

        container = manager._ensure_container(client, "deploy_default")

        self.assertEqual(container.id, "created-container")
        run_kwargs = client.containers.last_run_kwargs
        self.assertIsNotNone(run_kwargs)
        self.assertEqual(run_kwargs["image"], "redpandadata/redpanda:v26.1.9")
        self.assertEqual(run_kwargs["environment"], {})
        self.assertIn("command", run_kwargs)
        self.assertEqual(run_kwargs["network"], "deploy_default")


if __name__ == "__main__":
    unittest.main()
