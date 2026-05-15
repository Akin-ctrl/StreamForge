"""Tests for Kafka container discovery helpers."""

from __future__ import annotations

import unittest

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

    def get(self, target: str):
        for container in self._containers:
            if container.name == target or container.id == target:
                return container
        raise RuntimeError("not found")

    def list(self, all: bool = False):  # noqa: ARG002 - docker-compatible signature
        return list(self._containers)


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


if __name__ == "__main__":
    unittest.main()
