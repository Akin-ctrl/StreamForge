"""Kafka forwarding sink service.

Consumes validated internal topics from the gateway Kafka cluster and republishes
them to a configured target Kafka topic, typically on an external cluster.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import threading
from contextlib import suppress

from fastapi import FastAPI
import uvicorn

from adapters.adapter_base.schema import SchemaManager
from gateway_runtime.circuit_breaker import CircuitBreaker
from gateway_runtime.logging_utils import configure_json_logging


APP = FastAPI(title="sink-kafka", version="0.1.0")

_STOP = threading.Event()
_TARGET_BREAKER = CircuitBreaker(
    name="kafka_sink",
    failure_threshold=int(os.getenv("SINK_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")),
    open_duration_seconds=float(os.getenv("SINK_CIRCUIT_BREAKER_OPEN_SECONDS", "30")),
)
_STATS = {
    "consumed": 0,
    "published": 0,
    "errors": 0,
    "last_error": None,
    "consumer_lag": 0,
}
_AGGREGATE_SCHEMA_PATH = str(Path(__file__).resolve().parents[2] / "schemas" / "telemetry_aggregate.avsc")
_EVENT_SCHEMA_PATH = str(Path(__file__).resolve().parents[2] / "schemas" / "event.avsc")
_ALARM_SCHEMA_PATH = str(Path(__file__).resolve().parents[2] / "schemas" / "alarm.avsc")


def _load_config() -> dict:
    raw = os.getenv("SINK_CONFIG", "{}")
    config = json.loads(raw)
    source_topic = config.get("source_topic") or config.get("topic", "telemetry.clean")
    target_topic = config.get("target_topic", source_topic)
    return {
        "source_bootstrap": config.get("source_bootstrap", config.get("kafka_bootstrap", os.getenv("KAFKA_BOOTSTRAP", "kafka:9092"))),
        "source_topic": source_topic,
        "group_id": config.get("group_id", "sf-sink-kafka"),
        "target_bootstrap": config.get("target_bootstrap", config.get("kafka_bootstrap", os.getenv("KAFKA_BOOTSTRAP", "kafka:9092"))),
        "target_topic": target_topic,
        "message_format": config.get("message_format", "auto"),
        "schema_path": config.get("schema_path"),
        "schema_registry_url": config.get("schema_registry_url", os.getenv("SCHEMA_REGISTRY_URL", "")),
        "schema_cache_path": config.get("schema_cache_path", os.getenv("SCHEMA_CACHE_PATH", "/data/schemas.cache.json")),
        "target_schema_registry_url": config.get("target_schema_registry_url", config.get("schema_registry_url", os.getenv("SCHEMA_REGISTRY_URL", ""))),
        "target_schema_cache_path": config.get("target_schema_cache_path", config.get("schema_cache_path", os.getenv("SCHEMA_CACHE_PATH", "/data/schemas.cache.json"))),
        "target_schema_subject": config.get("target_schema_subject"),
        "preserve_key": bool(config.get("preserve_key", True)),
    }


def _resolve_schema(topic: str, schema_path: str | None, message_format: str = "auto", registry_url: str = "", cache_path: str = "/data/schemas.cache.json", schema_subject: str | None = None) -> SchemaManager:
    resolved_path = schema_path
    if resolved_path is None and (message_format == "aggregate" or topic.startswith("telemetry.1")):
        resolved_path = _AGGREGATE_SCHEMA_PATH
    if resolved_path is None and (message_format == "event" or topic.startswith("events.")):
        resolved_path = _EVENT_SCHEMA_PATH
    if resolved_path is None and (message_format == "alarm" or topic.startswith("alarms.")):
        resolved_path = _ALARM_SCHEMA_PATH
    output = {
        "topic": topic,
        "schema_registry_url": registry_url,
        "schema_cache_path": cache_path,
    }
    if resolved_path:
        output["schema_path"] = resolved_path
    if schema_subject:
        output["schema_subject"] = schema_subject
    return SchemaManager({"output": output})


def _message_format(topic: str, configured_format: str) -> str:
    if configured_format in {"telemetry", "aggregate", "event", "alarm"}:
        return configured_format
    if topic.startswith("telemetry.1"):
        return "aggregate"
    if topic.startswith("events."):
        return "event"
    if topic.startswith("alarms."):
        return "alarm"
    return "telemetry"


def _serialize_key(value: str | bytes | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8")


def _commit_consumer_record(consumer, record) -> None:
    from kafka.structs import OffsetAndMetadata, TopicPartition  # type: ignore

    leader_epoch = getattr(record, "leader_epoch", -1)
    consumer.commit(
        {
            TopicPartition(record.topic, record.partition): OffsetAndMetadata(
                record.offset + 1,
                None,
                leader_epoch,
            ),
        }
    )


def _writer_loop() -> None:
    cfg = _load_config()

    try:
        from kafka import KafkaConsumer, KafkaProducer  # type: ignore
    except ModuleNotFoundError as exc:
        _STATS["errors"] += 1
        _STATS["last_error"] = str(exc)
        return

    while not _STOP.is_set():
        if not _TARGET_BREAKER.allow_request():
            _STOP.wait(timeout=max(_TARGET_BREAKER.remaining_open_seconds(), 1.0))
            continue

        consumer = None
        producer = None
        try:
            resolved_format = _message_format(cfg["source_topic"], cfg["message_format"])
            source_schema = _resolve_schema(
                topic=cfg["source_topic"],
                schema_path=cfg.get("schema_path"),
                message_format=resolved_format,
                registry_url=str(cfg.get("schema_registry_url", "")),
                cache_path=str(cfg.get("schema_cache_path", "/data/schemas.cache.json")),
            )
            target_schema = _resolve_schema(
                topic=cfg["target_topic"],
                schema_path=cfg.get("schema_path"),
                message_format=resolved_format,
                registry_url=str(cfg.get("target_schema_registry_url", "")),
                cache_path=str(cfg.get("target_schema_cache_path", "/data/schemas.cache.json")),
                schema_subject=cfg.get("target_schema_subject"),
            )
            consumer = KafkaConsumer(
                cfg["source_topic"],
                bootstrap_servers=cfg["source_bootstrap"],
                group_id=cfg["group_id"],
                auto_offset_reset="latest",
                enable_auto_commit=False,
                value_deserializer=source_schema.decode,
            )
            producer = KafkaProducer(
                bootstrap_servers=cfg["target_bootstrap"],
                key_serializer=_serialize_key,
                value_serializer=target_schema.encode,
                acks=os.getenv("SINK_KAFKA_ACKS", "all"),
                retries=int(os.getenv("SINK_KAFKA_RETRIES", "3")),
            )

            for record in consumer:
                if _STOP.is_set():
                    break

                key = record.key if cfg.get("preserve_key", True) else None
                future = producer.send(cfg["target_topic"], key=key, value=record.value)
                future.get(timeout=float(os.getenv("SINK_KAFKA_SEND_TIMEOUT_S", "10")))
                producer.flush()
                _commit_consumer_record(consumer, record)
                _STATS["consumed"] += 1
                _STATS["published"] += 1
                _STATS["last_error"] = None
                _STATS["consumer_lag"] = 0
                _TARGET_BREAKER.record_success()
        except Exception as exc:
            _STATS["errors"] += 1
            _STATS["last_error"] = str(exc)
            _TARGET_BREAKER.record_failure(exc)
            _STOP.wait(timeout=max(_TARGET_BREAKER.remaining_open_seconds(), 3.0))
        finally:
            with suppress(Exception):
                if producer is not None:
                    producer.flush()
                    producer.close()
            with suppress(Exception):
                if consumer is not None:
                    consumer.close()


def _health_payload() -> dict:
    breaker = _TARGET_BREAKER.snapshot()
    status = "healthy"
    if breaker.state == "open":
        status = "failed"
    elif breaker.state == "half_open" or _STATS["last_error"] is not None:
        status = "degraded"
    return {
        "status": status,
        "stats": _STATS,
        "circuit_breaker": {
            "name": breaker.name,
            "state": breaker.state,
            "consecutive_failures": breaker.consecutive_failures,
            "failure_threshold": breaker.failure_threshold,
            "open_remaining_seconds": breaker.open_remaining_seconds,
            "last_error": breaker.last_error,
        },
    }


@APP.get("/health")
def health() -> dict:
    return _health_payload()


@APP.get("/metrics")
def metrics() -> str:
    lines = [
        "# TYPE sink_kafka_consumed_total counter",
        f"sink_kafka_consumed_total {_STATS['consumed']}",
        "# TYPE sink_kafka_published_total counter",
        f"sink_kafka_published_total {_STATS['published']}",
        "# TYPE sink_kafka_errors_total counter",
        f"sink_kafka_errors_total {_STATS['errors']}",
        "# TYPE sink_kafka_consumer_lag gauge",
        f"sink_kafka_consumer_lag {_STATS['consumer_lag']}",
    ]
    return "\n".join(lines) + "\n"


def _start_background() -> None:
    thread = threading.Thread(target=_writer_loop, daemon=True)
    thread.start()


def _shutdown(*_args) -> None:
    _STOP.set()


def main() -> None:
    configure_json_logging(os.getenv("LOG_LEVEL", "INFO"))
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    _start_background()
    uvicorn.run(APP, host="0.0.0.0", port=int(os.getenv("SINK_HEALTH_PORT", "8091")))


if __name__ == "__main__":
    main()
