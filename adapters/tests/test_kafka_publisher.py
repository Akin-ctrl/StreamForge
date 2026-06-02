"""Tests for shared adapter Kafka publishing behavior."""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from adapters.adapter_base.kafka_publisher import KafkaPublisher


class FakeRecordMetadata:
    def __init__(self, partition: int = 2, offset: int = 17) -> None:
        self.partition = partition
        self.offset = offset


class FakeFuture:
    def __init__(self, metadata: FakeRecordMetadata | None = None, error: Exception | None = None) -> None:
        self._metadata = metadata or FakeRecordMetadata()
        self._error = error

    def get(self, timeout: float | None = None):
        if self._error is not None:
            raise self._error
        return self._metadata


class FakeKafkaProducer:
    instances: list["FakeKafkaProducer"] = []
    fail_with: Exception | None = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.send_calls: list[dict[str, object]] = []
        self.flush_calls = 0
        self.close_calls = 0
        FakeKafkaProducer.instances.append(self)

    def send(self, topic: str, key=None, value=None):
        self.send_calls.append({"topic": topic, "key": key, "value": value})
        return FakeFuture(error=FakeKafkaProducer.fail_with)

    def flush(self) -> None:
        self.flush_calls += 1

    def close(self) -> None:
        self.close_calls += 1

    @classmethod
    def reset(cls) -> None:
        cls.instances = []
        cls.fail_with = None


class KafkaPublisherTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeKafkaProducer.reset()
        fake_module = types.SimpleNamespace(KafkaProducer=FakeKafkaProducer)
        self.kafka_patch = patch.dict(sys.modules, {"kafka": fake_module})
        self.kafka_patch.start()
        self.addCleanup(self.kafka_patch.stop)
        self.config = {
            "output": {
                "kafka_bootstrap": "localhost:9092",
                "topic": "telemetry.raw",
            }
        }

    def test_publish_uses_shared_producer_defaults_and_asset_key(self) -> None:
        publisher = KafkaPublisher(self.config)

        result = publisher.publish({"asset_id": "asset-1", "value": 42})

        producer = FakeKafkaProducer.instances[0]
        self.assertEqual(producer.kwargs["bootstrap_servers"], "localhost:9092")
        self.assertEqual(producer.kwargs["acks"], "all")
        self.assertEqual(producer.kwargs["retries"], 3)
        self.assertEqual(result["topic"], "telemetry.raw")
        self.assertEqual(result["key"], "asset-1")
        self.assertEqual(result["partition"], 2)
        self.assertEqual(result["offset"], 17)
        self.assertEqual(producer.send_calls[0]["topic"], "telemetry.raw")
        self.assertEqual(producer.send_calls[0]["key"], "asset-1")
        self.assertEqual(producer.send_calls[0]["value"], {"asset_id": "asset-1", "value": 42})
        self.assertEqual(producer.kwargs["key_serializer"]("asset-1"), b"asset-1")
        self.assertEqual(producer.kwargs["value_serializer"]({"value": 42}), b'{"value": 42}')

        health = publisher.health()
        self.assertEqual(health["published_messages"], 1)
        self.assertEqual(health["publish_failures"], 0)
        self.assertEqual(health["last_publish_key"], "asset-1")

    def test_publish_without_asset_id_uses_no_key(self) -> None:
        publisher = KafkaPublisher(self.config)

        result = publisher.publish({"value": 42})

        producer = FakeKafkaProducer.instances[0]
        self.assertIsNone(producer.send_calls[0]["key"])
        self.assertIsNone(result["key"])

    def test_publish_failure_updates_health_and_raises(self) -> None:
        FakeKafkaProducer.fail_with = TimeoutError("timed out")
        publisher = KafkaPublisher(self.config)

        with self.assertRaisesRegex(RuntimeError, "Kafka-compatible publish failed"):
            publisher.publish({"asset_id": "asset-1", "value": 42})

        health = publisher.health()
        self.assertEqual(health["published_messages"], 0)
        self.assertEqual(health["publish_failures"], 1)
        self.assertEqual(health["last_error"], "timed out")

    def test_close_flushes_and_closes_producer(self) -> None:
        publisher = KafkaPublisher(self.config)
        publisher.publish({"asset_id": "asset-1", "value": 42})

        publisher.close()

        producer = FakeKafkaProducer.instances[0]
        self.assertEqual(producer.flush_calls, 1)
        self.assertEqual(producer.close_calls, 1)


if __name__ == "__main__":
    unittest.main()
