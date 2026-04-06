"""Shared Kafka publishing behavior for adapter containers."""

from __future__ import annotations

import os
from typing import Any, Dict

from .schema import SchemaManager


class KafkaPublisher:
    """Centralized adapter-side Kafka publisher for local edge topics."""

    def __init__(self, config: dict) -> None:
        self._config = config
        self._schema = SchemaManager(config)
        self._producer = None
        self._send_timeout_s = float(os.getenv("ADAPTER_KAFKA_SEND_TIMEOUT_S", "10"))
        self._acks = os.getenv("ADAPTER_KAFKA_ACKS", "all")
        self._retries = int(os.getenv("ADAPTER_KAFKA_RETRIES", "3"))
        self._health: Dict[str, object] = {
            "published_messages": 0,
            "publish_failures": 0,
            "last_publish_topic": self.topic,
            "last_publish_key": None,
            "last_publish_partition": None,
            "last_publish_offset": None,
            "last_error": None,
            "serialization_format": "avro" if os.getenv("SCHEMA_STRICT_AVRO", "false").lower() in {"1", "true", "yes", "on"} else "avro_or_json_fallback",
        }

    @property
    def topic(self) -> str:
        """Kafka topic for adapter output."""
        return str(self._output()["topic"])

    @property
    def bootstrap(self) -> str:
        """Kafka bootstrap address for adapter output."""
        return str(self._output()["kafka_bootstrap"])

    def publish(self, message: dict[str, object]) -> Dict[str, object]:
        """Publish a normalized message and wait for broker acknowledgement."""
        producer = self._producer_or_create()
        key = self._message_key(message)
        try:
            future = producer.send(self.topic, key=key, value=message)
            record_metadata = future.get(timeout=self._send_timeout_s)
        except Exception as exc:
            self._health["publish_failures"] = int(self._health["publish_failures"]) + 1
            self._health["last_error"] = str(exc)
            raise RuntimeError(f"Kafka publish failed for topic {self.topic}: {exc}") from exc

        self._health["published_messages"] = int(self._health["published_messages"]) + 1
        if isinstance(key, bytes):
            last_key = key.decode("utf-8")
        else:
            last_key = key
        self._health["last_publish_key"] = last_key
        self._health["last_publish_partition"] = getattr(record_metadata, "partition", None)
        self._health["last_publish_offset"] = getattr(record_metadata, "offset", None)
        self._health["last_error"] = None
        return {
            "topic": self.topic,
            "key": self._health["last_publish_key"],
            "partition": self._health["last_publish_partition"],
            "offset": self._health["last_publish_offset"],
        }

    def close(self) -> None:
        """Flush and close the Kafka producer if it was initialized."""
        if self._producer is None:
            return
        try:
            self._producer.flush()
            self._producer.close()
        finally:
            self._producer = None

    def health(self) -> Dict[str, object]:
        """Return publishing health and counters."""
        return dict(self._health)

    def _producer_or_create(self):
        if self._producer is None:
            try:
                from kafka import KafkaProducer  # type: ignore
            except ModuleNotFoundError as exc:
                raise RuntimeError("kafka-python is required for adapter Kafka publishing") from exc

            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap,
                acks=self._acks,
                retries=self._retries,
                key_serializer=self._serialize_key,
                value_serializer=self._schema.encode,
            )
        return self._producer

    def _output(self) -> dict[str, object]:
        output = self._config.get("output")
        if not isinstance(output, dict):
            raise RuntimeError("Adapter config must include an 'output' object")
        if "kafka_bootstrap" not in output or "topic" not in output:
            raise RuntimeError("Adapter output must include 'kafka_bootstrap' and 'topic'")
        return output

    @staticmethod
    def _message_key(message: dict[str, object]) -> str | None:
        asset_id = message.get("asset_id")
        return asset_id if isinstance(asset_id, str) and asset_id else None

    @staticmethod
    def _serialize_key(value: str | bytes | None) -> bytes | None:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        return value.encode("utf-8")
