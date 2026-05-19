"""HTTP forwarding sink service.

Consumes validated internal topics from the gateway Kafka cluster and republishes
them as JSON to a configured HTTP endpoint.
"""

from __future__ import annotations

import base64
from contextlib import suppress
import json
import os
from pathlib import Path
import signal
import threading
from urllib import error, request

from fastapi import FastAPI
import uvicorn

from adapters.adapter_base.schema import SchemaManager
from gateway_runtime.circuit_breaker import CircuitBreaker
from gateway_runtime.logging_utils import configure_json_logging


APP = FastAPI(title="sink-http", version="0.1.0")

_STOP = threading.Event()
_HTTP_BREAKER = CircuitBreaker(
    name="http_sink",
    failure_threshold=int(os.getenv("SINK_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")),
    open_duration_seconds=float(os.getenv("SINK_CIRCUIT_BREAKER_OPEN_SECONDS", "30")),
)
_STATS = {
    "consumed": 0,
    "delivered": 0,
    "errors": 0,
    "last_error": None,
    "last_response_status": None,
    "consumer_lag": 0,
}
_AGGREGATE_SCHEMA_PATH = str(Path(__file__).resolve().parents[2] / "schemas" / "telemetry_aggregate.avsc")
_EVENT_SCHEMA_PATH = str(Path(__file__).resolve().parents[2] / "schemas" / "event.avsc")
_ALARM_SCHEMA_PATH = str(Path(__file__).resolve().parents[2] / "schemas" / "alarm.avsc")


def _kafka_runtime_error_types() -> tuple[type[BaseException], ...]:
    """Return the consumer-side exceptions expected during sink shutdown."""
    error_types: list[type[BaseException]] = [RuntimeError, OSError, ValueError]
    try:
        from kafka.errors import KafkaError  # type: ignore
    except ModuleNotFoundError:
        return tuple(error_types)
    return tuple(error_types + [KafkaError])


def _load_config() -> dict:
    raw = os.getenv("SINK_CONFIG", "{}")
    config = json.loads(raw)
    source_topic = config.get("source_topic") or config.get("topic", "telemetry.clean")
    headers = dict(config.get("headers") or {})
    username = config.get("basic_auth_username")
    password = config.get("basic_auth_password")
    if username and password and "Authorization" not in headers:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    headers.setdefault("Content-Type", "application/json")
    return {
        "source_bootstrap": config.get("source_bootstrap", config.get("kafka_bootstrap", os.getenv("KAFKA_BOOTSTRAP", "kafka:9092"))),
        "source_topic": source_topic,
        "group_id": config.get("group_id", "sf-sink-http"),
        "url": config.get("url"),
        "method": str(config.get("method", "POST")).upper(),
        "headers": headers,
        "timeout_seconds": float(config.get("timeout_seconds", os.getenv("SINK_HTTP_TIMEOUT_SECONDS", "10"))),
        "message_format": config.get("message_format", "auto"),
        "schema_path": config.get("schema_path"),
        "schema_registry_url": config.get("schema_registry_url", os.getenv("SCHEMA_REGISTRY_URL", "")),
        "schema_cache_path": config.get("schema_cache_path", os.getenv("SCHEMA_CACHE_PATH", "/data/schemas.cache.json")),
    }


def _resolve_schema(topic: str, schema_path: str | None, message_format: str = "auto", registry_url: str = "", cache_path: str = "/data/schemas.cache.json") -> SchemaManager:
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


def _send_http(cfg: dict, payload: dict) -> int:
    if not cfg.get("url"):
        raise RuntimeError("HTTP sink config requires 'url'")
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        cfg["url"],
        data=body,
        method=cfg["method"],
        headers=cfg["headers"],
    )
    try:
        with request.urlopen(req, timeout=cfg["timeout_seconds"]) as response:
            status = response.status if hasattr(response, "status") else response.getcode()
    except error.HTTPError as exc:
        status = int(exc.code)
        raise RuntimeError(f"HTTP sink request failed with status {status}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"HTTP sink request failed: {exc.reason}") from exc

    if status < 200 or status >= 300:
        raise RuntimeError(f"HTTP sink request failed with status {status}")
    return int(status)


def _writer_loop() -> None:
    cfg = _load_config()

    try:
        from kafka import KafkaConsumer  # type: ignore
    except ModuleNotFoundError as exc:
        _STATS["errors"] += 1
        _STATS["last_error"] = str(exc)
        return

    while not _STOP.is_set():
        if not _HTTP_BREAKER.allow_request():
            _STOP.wait(timeout=max(_HTTP_BREAKER.remaining_open_seconds(), 1.0))
            continue

        consumer = None
        try:
            resolved_format = _message_format(cfg["source_topic"], cfg["message_format"])
            source_schema = _resolve_schema(
                topic=cfg["source_topic"],
                schema_path=cfg.get("schema_path"),
                message_format=resolved_format,
                registry_url=str(cfg.get("schema_registry_url", "")),
                cache_path=str(cfg.get("schema_cache_path", "/data/schemas.cache.json")),
            )
            consumer = KafkaConsumer(
                cfg["source_topic"],
                bootstrap_servers=cfg["source_bootstrap"],
                group_id=cfg["group_id"],
                auto_offset_reset="latest",
                enable_auto_commit=False,
                value_deserializer=source_schema.decode,
            )

            for record in consumer:
                if _STOP.is_set():
                    break
                status = _send_http(cfg, record.value)
                _commit_consumer_record(consumer, record)
                _STATS["consumed"] += 1
                _STATS["delivered"] += 1
                _STATS["last_response_status"] = status
                _STATS["last_error"] = None
                _STATS["consumer_lag"] = 0
                _HTTP_BREAKER.record_success()
        except Exception as exc:
            # Deliberate service-boundary catch: the sink should trip its
            # breaker and retry instead of crashing the background thread.
            _STATS["errors"] += 1
            _STATS["last_error"] = str(exc)
            _HTTP_BREAKER.record_failure(exc)
            _STOP.wait(timeout=max(_HTTP_BREAKER.remaining_open_seconds(), 3.0))
        finally:
            if consumer is not None:
                with suppress(*_kafka_runtime_error_types()):
                    consumer.close()


def _health_payload() -> dict:
    breaker = _HTTP_BREAKER.snapshot()
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
        "# TYPE sink_http_consumed_total counter",
        f"sink_http_consumed_total {_STATS['consumed']}",
        "# TYPE sink_http_delivered_total counter",
        f"sink_http_delivered_total {_STATS['delivered']}",
        "# TYPE sink_http_errors_total counter",
        f"sink_http_errors_total {_STATS['errors']}",
        "# TYPE sink_http_consumer_lag gauge",
        f"sink_http_consumer_lag {_STATS['consumer_lag']}",
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
