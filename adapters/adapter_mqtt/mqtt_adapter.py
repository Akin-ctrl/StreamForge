"""MQTT adapter implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from adapters.adapter_base.base_adapter import BaseAdapter
from adapters.adapter_base.kafka_publisher import KafkaPublisher


_EVENT_SCHEMA_PATH = str(Path(__file__).resolve().parents[2] / "schemas" / "event.avsc")


@dataclass(frozen=True)
class FieldMapping:
    field: str
    parameter: str
    unit: str


@dataclass(frozen=True)
class SubscriptionSpec:
    topic: str
    payload_format: str
    message_type: str
    asset_id: str | None
    mappings: tuple[FieldMapping, ...]


class MqttAdapter(BaseAdapter):
    """MQTT ingress adapter for telemetry and explicit event payloads."""

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._client = None
        self._event_publisher: KafkaPublisher | None = None
        self._queue: Queue[dict[str, Any]] = Queue()
        self._connected_event = None
        self._subscriptions = self._load_subscriptions()
        self._health.update(
            {
                "transport": "mqtt",
                "broker_host": str(config.get("broker_host", "")),
                "broker_port": int(config.get("broker_port", 1883)),
                "subscribed_topics": [spec.topic for spec in self._subscriptions],
                "subscribed_topic_count": len(self._subscriptions),
                "received_messages": 0,
                "parsed_messages": 0,
                "parse_failures": 0,
                "ignored_messages": 0,
                "last_message_topic": None,
                "last_message_type": None,
                "events_topic": self._events_topic,
                "published_events": 0,
                "event_publish_failures": 0,
                "last_event_publish_at": None,
                "last_event_publish_key": None,
                "last_event_publish_partition": None,
                "last_event_publish_offset": None,
            }
        )

    def connect(self) -> None:
        """Connect to the MQTT broker and subscribe to configured topics."""
        client = self._create_client(str(self.config.get("client_id", f"streamforge-{self._adapter_id}")))
        username = str(self.config.get("username", "") or "")
        password = str(self.config.get("password", "") or "")
        if username:
            client.username_pw_set(username, password=password or None)

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        self._connected_event = self._event_factory()
        host = str(self.config.get("broker_host") or self.config.get("host") or "").strip()
        if not host:
            raise RuntimeError("MQTT adapter requires 'broker_host'")
        port = int(self.config.get("broker_port", 1883))
        keepalive = int(self.config.get("keepalive_seconds", 60))
        client.connect(host, port, keepalive)
        client.loop_start()
        if not self._connected_event.wait(timeout=float(self.config.get("connect_timeout_seconds", 5))):
            raise RuntimeError(f"Timed out connecting to MQTT broker {host}:{port}")
        self._client = client
        self._health["connected"] = True

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.loop_stop()
            except Exception:
                pass
            try:
                self._client.disconnect()
            finally:
                self._client = None
        if self._event_publisher is not None:
            self._event_publisher.close()
        self._health["connected"] = False

    def run(self) -> None:
        """Run the push-based MQTT lifecycle until shutdown."""
        previous_handlers = self._install_signal_handlers()
        try:
            self._set_status("starting", connected=False, running=False, last_error=None)
            self.connect()
            self._set_status("healthy", connected=True, running=True, last_error=None)

            while not self._stop_event.is_set():
                raw = self.poll()
                if raw is None:
                    continue
                self._health["last_poll_at"] = self._utcnow()
                message = self.transform(raw)
                self.publish(message)
                self._health["last_publish_at"] = self._utcnow()
                self._set_status("healthy", connected=True, running=True, last_error=None)
        except Exception as exc:
            self._set_status("failed", running=False, last_error=str(exc))
            raise
        finally:
            try:
                self.disconnect()
            finally:
                if self._publisher is not None:
                    self._publisher.close()
                status = "stopped" if self._health.get("status") != "failed" else "failed"
                self._set_status(status, connected=False, running=False)
                self._restore_signal_handlers(previous_handlers)

    def poll(self) -> dict[str, Any] | None:
        """Block until an MQTT message arrives or shutdown is requested."""
        while not self._stop_event.is_set():
            try:
                return self._queue.get(timeout=0.5)
            except Empty:
                continue
        return None

    def transform(self, raw: dict[str, Any]) -> dict[str, object]:
        """Map queued MQTT payloads into normalized telemetry or event messages."""
        now = datetime.now(timezone.utc).isoformat()
        pipeline_id = str(self.config.get("output", {}).get("pipeline_id") or self.config.get("output", {}).get("asset_id") or self._adapter_id)
        if raw["message_type"] == "event":
            payload = raw["payload"]
            return {
                "telemetry": None,
                "events": [
                    {
                        "asset_id": raw["asset_id"] or self.config.get("output", {}).get("asset_id") or self._adapter_id,
                        "event_type": str(payload.get("event_type", "mqtt_event")),
                        "classification": "EVENT",
                        "previous_state": dict(payload.get("previous_state") or {}),
                        "new_state": dict(payload.get("new_state") or {}),
                        "timestamps": {
                            "device_time": payload.get("device_time"),
                            "gateway_time": now,
                        },
                        "metadata": {
                            "adapter_id": self._adapter_id,
                            "pipeline_id": pipeline_id,
                        },
                    }
                ],
            }

        readings: list[dict[str, object]] = []
        payload = raw["payload"]
        for mapping in raw["mappings"]:
            if mapping.field not in payload:
                continue
            readings.append(
                {
                    "parameter": mapping.parameter,
                    "value": payload[mapping.field],
                    "unit": mapping.unit,
                    "quality": "GOOD",
                    "device_time": payload.get("device_time"),
                }
            )

        return {
            "telemetry": {
                "asset_id": raw["asset_id"] or self.config.get("output", {}).get("asset_id") or self._adapter_id,
                "gateway_time": now,
                "readings": readings,
            },
            "events": [],
        }

    def publish(self, message: dict[str, object]) -> None:
        telemetry_message = message.get("telemetry")
        if isinstance(telemetry_message, dict) and telemetry_message.get("readings"):
            if self._publisher is None:
                self._publisher = KafkaPublisher(self.config)
            publish_metadata = self._publisher.publish(telemetry_message)
            publish_health = self._publisher.health()
            self._health["last_publish_topic"] = publish_metadata["topic"]
            self._health["last_publish_key"] = publish_metadata["key"]
            self._health["last_publish_partition"] = publish_metadata["partition"]
            self._health["last_publish_offset"] = publish_metadata["offset"]
            self._health["last_error"] = publish_health["last_error"]

        events = message.get("events", [])
        if self._events_topic and isinstance(events, list) and events:
            if self._event_publisher is None:
                self._event_publisher = KafkaPublisher(self._event_publisher_config())
            for event_message in events:
                publish_metadata = self._event_publisher.publish(event_message)
                event_health = self._event_publisher.health()
                self._health["last_event_publish_at"] = self._utcnow()
                self._health["last_event_publish_key"] = publish_metadata["key"]
                self._health["last_event_publish_partition"] = publish_metadata["partition"]
                self._health["last_event_publish_offset"] = publish_metadata["offset"]
                self._health["published_events"] = event_health["published_messages"]
                self._health["event_publish_failures"] = event_health["publish_failures"]
                self._health["last_error"] = event_health["last_error"]

    def health(self) -> dict[str, object]:
        snapshot = dict(self._health)
        telemetry_health = self._publisher.health() if self._publisher is not None else None
        event_health = self._event_publisher.health() if self._event_publisher is not None else None
        if telemetry_health is not None:
            snapshot["telemetry_publish"] = telemetry_health
        if event_health is not None:
            snapshot["event_publish"] = event_health
        snapshot["published_messages"] = int((telemetry_health or {}).get("published_messages", 0)) + int(
            snapshot.get("published_events", 0)
        )
        snapshot["publish_failures"] = int((telemetry_health or {}).get("publish_failures", 0)) + int(
            snapshot.get("event_publish_failures", 0)
        )
        snapshot["last_publish_topic"] = snapshot.get("last_publish_topic") or self.config.get("output", {}).get("topic")
        snapshot["last_error"] = snapshot.get("last_error") or (telemetry_health or {}).get("last_error") or (event_health or {}).get("last_error")
        return snapshot

    def _load_subscriptions(self) -> tuple[SubscriptionSpec, ...]:
        specs: list[SubscriptionSpec] = []
        for item in self.config.get("subscriptions", []):
            if not isinstance(item, dict):
                continue
            mappings = tuple(
                FieldMapping(
                    field=str(mapping["field"]),
                    parameter=str(mapping.get("parameter") or mapping["field"]),
                    unit=str(mapping.get("unit", "")),
                )
                for mapping in item.get("mappings", [])
                if isinstance(mapping, dict) and "field" in mapping
            )
            specs.append(
                SubscriptionSpec(
                    topic=str(item["topic"]),
                    payload_format=str(item.get("payload_format", "json")),
                    message_type=str(item.get("message_type", "telemetry")),
                    asset_id=str(item["asset_id"]) if item.get("asset_id") else None,
                    mappings=mappings,
                )
            )
        if not specs:
            raise RuntimeError("MQTT adapter requires at least one subscription")
        return tuple(specs)

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties=None) -> None:
        code = int(reason_code) if not isinstance(reason_code, int) else reason_code
        if code != 0:
            self._health["last_error"] = f"MQTT connect failed with code {code}"
            return
        for spec in self._subscriptions:
            client.subscribe(spec.topic, qos=int(self.config.get("qos", 1)))
        self._connected_event.set()

    def _on_message(self, _client, _userdata, msg) -> None:
        self._health["received_messages"] = int(self._health.get("received_messages", 0)) + 1
        self._health["last_message_topic"] = getattr(msg, "topic", None)
        self._ingest_message(str(msg.topic), bytes(msg.payload))

    def _ingest_message(self, topic: str, payload_bytes: bytes) -> None:
        spec = self._match_subscription(topic)
        if spec is None:
            self._health["ignored_messages"] = int(self._health.get("ignored_messages", 0)) + 1
            return
        try:
            payload = self._parse_payload(spec, payload_bytes)
        except Exception as exc:
            self._health["parse_failures"] = int(self._health.get("parse_failures", 0)) + 1
            self._health["last_error"] = str(exc)
            self._set_status("degraded", connected=True, running=bool(self._health.get("running")), last_error=str(exc))
            return

        self._queue.put(
            {
                "topic": topic,
                "message_type": spec.message_type,
                "asset_id": spec.asset_id,
                "mappings": spec.mappings,
                "payload": payload,
            }
        )
        self._health["parsed_messages"] = int(self._health.get("parsed_messages", 0)) + 1
        self._health["last_message_type"] = spec.message_type

    def _parse_payload(self, spec: SubscriptionSpec, payload_bytes: bytes) -> dict[str, Any]:
        if spec.payload_format != "json":
            raise RuntimeError(f"Unsupported MQTT payload_format: {spec.payload_format}")
        try:
            decoded = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid MQTT JSON payload on topic {spec.topic}") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError(f"MQTT payload on topic {spec.topic} must be a JSON object")
        return decoded

    def _match_subscription(self, topic: str) -> SubscriptionSpec | None:
        for spec in self._subscriptions:
            if spec.topic == topic or self._topic_matches(spec.topic, topic):
                return spec
        return None

    @staticmethod
    def _topic_matches(subscription: str, topic: str) -> bool:
        try:
            from paho.mqtt.client import topic_matches_sub  # type: ignore
        except Exception:
            return subscription == topic
        return bool(topic_matches_sub(subscription, topic))

    @staticmethod
    def _event_factory():
        from threading import Event

        return Event()

    @staticmethod
    def _create_client(client_id: str):
        try:
            import paho.mqtt.client as mqtt  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("paho-mqtt is required for MqttAdapter") from exc

        if hasattr(mqtt, "CallbackAPIVersion"):
            return mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1, client_id=client_id)
        return mqtt.Client(client_id=client_id)

    @property
    def _events_topic(self) -> str | None:
        output = self.config.get("output")
        if not isinstance(output, dict):
            return None
        topic = output.get("events_topic")
        return str(topic) if topic else None

    def _event_publisher_config(self) -> dict:
        output = dict(self.config.get("output", {}))
        output["topic"] = self._events_topic
        output["schema_path"] = _EVENT_SCHEMA_PATH
        return {
            **self.config,
            "output": output,
        }
