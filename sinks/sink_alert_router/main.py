"""Alert-routing sink service.

Consumes alarm messages from the internal gateway Kafka cluster and forwards
them to webhook-style destinations such as generic HTTP endpoints and Slack.
"""

from __future__ import annotations

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


APP = FastAPI(title="sink-alert-router", version="0.1.0")

_STOP = threading.Event()
_ALERT_BREAKER = CircuitBreaker(
    name="alert_router_sink",
    failure_threshold=int(os.getenv("SINK_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")),
    open_duration_seconds=float(os.getenv("SINK_CIRCUIT_BREAKER_OPEN_SECONDS", "30")),
)
_STATS = {
    "consumed": 0,
    "delivered": 0,
    "errors": 0,
    "last_error": None,
    "last_delivery_status": None,
    "consumer_lag": 0,
    "route_type": "webhook",
}
_ALARM_SCHEMA_PATH = str(Path(__file__).resolve().parents[2] / "schemas" / "alarm.avsc")


def _load_config() -> dict:
    raw = os.getenv("SINK_CONFIG", "{}")
    config = json.loads(raw)
    headers = dict(config.get("headers") or {})
    headers.setdefault("Content-Type", "application/json")
    route_type = _route_type(str(config.get("route_type", "webhook")))
    webhook_url = config.get("webhook_url")
    url = config.get("url") or webhook_url
    return {
        "source_bootstrap": config.get("source_bootstrap", config.get("kafka_bootstrap", os.getenv("KAFKA_BOOTSTRAP", "kafka:9092"))),
        "source_topic": config.get("source_topic", "alarms.raw"),
        "group_id": config.get("group_id", "sf-sink-alert-router"),
        "route_type": route_type,
        "url": url,
        "timeout_seconds": float(config.get("timeout_seconds", os.getenv("SINK_HTTP_TIMEOUT_SECONDS", "10"))),
        "headers": headers,
        "channel": config.get("channel"),
        "username": config.get("username", "StreamForge"),
        "icon_emoji": config.get("icon_emoji"),
        "schema_path": config.get("schema_path", _ALARM_SCHEMA_PATH),
        "schema_registry_url": config.get("schema_registry_url", os.getenv("SCHEMA_REGISTRY_URL", "")),
        "schema_cache_path": config.get("schema_cache_path", os.getenv("SCHEMA_CACHE_PATH", "/data/schemas.cache.json")),
    }


def _route_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"slack", "webhook"}:
        return normalized
    raise RuntimeError(f"Unsupported alert route_type: {value}")


def _resolve_schema(cfg: dict) -> SchemaManager:
    return SchemaManager(
        {
            "output": {
                "topic": cfg["source_topic"],
                "schema_path": cfg["schema_path"],
                "schema_registry_url": cfg["schema_registry_url"],
                "schema_cache_path": cfg["schema_cache_path"],
            }
        }
    )


def _severity_emoji(severity: str) -> str:
    mapping = {
        "CRITICAL": ":rotating_light:",
        "HIGH": ":warning:",
        "MEDIUM": ":large_orange_diamond:",
        "LOW": ":large_yellow_circle:",
        "INFO": ":information_source:",
    }
    return mapping.get(str(severity).upper(), ":warning:")


def _format_slack_payload(alarm: dict, cfg: dict) -> dict:
    severity = str(alarm.get("severity", "INFO")).upper()
    state = str(alarm.get("state", "ACTIVE")).upper()
    value = alarm.get("value")
    threshold = alarm.get("threshold")
    unit = alarm.get("unit") or ""
    value_line = "n/a" if value is None else f"{value} {unit}".strip()
    threshold_line = "n/a" if threshold is None else f"{threshold} {unit}".strip()
    text = (
        f"{_severity_emoji(severity)} StreamForge alarm {severity} {state}: "
        f"{alarm.get('asset_id', 'unknown asset')} / {alarm.get('type', 'alarm')} - "
        f"{alarm.get('message', '')}"
    )
    payload = {
        "text": text,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{_severity_emoji(severity)} *{severity} {state}*\n{alarm.get('message', '')}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Asset:*\n{alarm.get('asset_id', 'n/a')}"},
                    {"type": "mrkdwn", "text": f"*Alarm ID:*\n{alarm.get('alarm_id', 'n/a')}"},
                    {"type": "mrkdwn", "text": f"*Type:*\n{alarm.get('type', 'n/a')}"},
                    {"type": "mrkdwn", "text": f"*Raised At:*\n{alarm.get('raised_at', 'n/a')}"},
                    {"type": "mrkdwn", "text": f"*Value:*\n{value_line}"},
                    {"type": "mrkdwn", "text": f"*Threshold:*\n{threshold_line}"},
                ],
            },
        ],
    }
    if cfg.get("channel"):
        payload["channel"] = cfg["channel"]
    if cfg.get("username"):
        payload["username"] = cfg["username"]
    if cfg.get("icon_emoji"):
        payload["icon_emoji"] = cfg["icon_emoji"]
    return payload


def _format_webhook_payload(alarm: dict) -> dict:
    return alarm


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


def _post_json(url: str, payload: dict, headers: dict, timeout_seconds: float) -> int:
    if not url:
        raise RuntimeError("Alert router sink requires 'url' or 'webhook_url'")
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST", headers=headers)
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            status = response.status if hasattr(response, "status") else response.getcode()
    except error.HTTPError as exc:
        status = int(exc.code)
        raise RuntimeError(f"Alert router request failed with status {status}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Alert router request failed: {exc.reason}") from exc
    if status < 200 or status >= 300:
        raise RuntimeError(f"Alert router request failed with status {status}")
    return int(status)


def _deliver(cfg: dict, alarm: dict) -> int:
    payload = _format_webhook_payload(alarm)
    if cfg["route_type"] == "slack":
        payload = _format_slack_payload(alarm, cfg)
    return _post_json(cfg["url"], payload, cfg["headers"], cfg["timeout_seconds"])


def _writer_loop() -> None:
    cfg = _load_config()
    _STATS["route_type"] = cfg["route_type"]
    try:
        from kafka import KafkaConsumer  # type: ignore
    except ModuleNotFoundError as exc:
        _STATS["errors"] += 1
        _STATS["last_error"] = str(exc)
        return

    while not _STOP.is_set():
        if not _ALERT_BREAKER.allow_request():
            _STOP.wait(timeout=max(_ALERT_BREAKER.remaining_open_seconds(), 1.0))
            continue

        consumer = None
        try:
            schema = _resolve_schema(cfg)
            consumer = KafkaConsumer(
                cfg["source_topic"],
                bootstrap_servers=cfg["source_bootstrap"],
                group_id=cfg["group_id"],
                auto_offset_reset="latest",
                enable_auto_commit=False,
                value_deserializer=schema.decode,
            )
            for record in consumer:
                if _STOP.is_set():
                    break
                status = _deliver(cfg, record.value)
                _commit_consumer_record(consumer, record)
                _STATS["consumed"] += 1
                _STATS["delivered"] += 1
                _STATS["last_delivery_status"] = status
                _STATS["last_error"] = None
                _STATS["consumer_lag"] = 0
                _ALERT_BREAKER.record_success()
        except Exception as exc:
            _STATS["errors"] += 1
            _STATS["last_error"] = str(exc)
            _ALERT_BREAKER.record_failure(exc)
            _STOP.wait(timeout=max(_ALERT_BREAKER.remaining_open_seconds(), 3.0))
        finally:
            if consumer is not None:
                try:
                    consumer.close()
                except Exception:
                    pass


def _health_payload() -> dict:
    breaker = _ALERT_BREAKER.snapshot()
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
        "# TYPE sink_alert_router_consumed_total counter",
        f"sink_alert_router_consumed_total {_STATS['consumed']}",
        "# TYPE sink_alert_router_delivered_total counter",
        f"sink_alert_router_delivered_total {_STATS['delivered']}",
        "# TYPE sink_alert_router_errors_total counter",
        f"sink_alert_router_errors_total {_STATS['errors']}",
        "# TYPE sink_alert_router_consumer_lag gauge",
        f"sink_alert_router_consumer_lag {_STATS['consumer_lag']}",
    ]
    return "\n".join(lines) + "\n"


def _start_background() -> None:
    threading.Thread(target=_writer_loop, daemon=True).start()


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
