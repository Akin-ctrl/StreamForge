"""Tests for the MQTT adapter mapping behavior."""

from __future__ import annotations

import json
import unittest

from adapters.adapter_mqtt.mqtt_adapter import MqttAdapter


class FakeEvent:
    def __init__(self) -> None:
        self.set_called = False

    def set(self) -> None:
        self.set_called = True

    def wait(self, timeout: float | None = None) -> bool:
        return self.set_called


class FakeMqttClient:
    def __init__(self) -> None:
        self.username = None
        self.password = None
        self.connect_args = None
        self.loop_started = False
        self.subscriptions: list[tuple[str, int]] = []
        self.on_connect = None
        self.on_message = None

    def username_pw_set(self, username: str, password: str | None = None) -> None:
        self.username = username
        self.password = password

    def connect(self, host: str, port: int, keepalive: int) -> None:
        self.connect_args = (host, port, keepalive)

    def loop_start(self) -> None:
        self.loop_started = True

    def loop_stop(self) -> None:
        self.loop_started = False

    def disconnect(self) -> None:
        return None

    def subscribe(self, topic: str, qos: int = 0) -> None:
        self.subscriptions.append((topic, qos))


class MqttAdapterTests(unittest.TestCase):
    def _telemetry_config(self) -> dict:
        return {
            "broker_host": "mqtt-broker",
            "broker_port": 1883,
            "client_id": "streamforge-mqtt-line-1",
            "qos": 1,
            "subscriptions": [
                {
                    "topic": "factory/line1/telemetry",
                    "payload_format": "json",
                    "message_type": "telemetry",
                    "asset_id": "line1_sensor_pack",
                    "mappings": [
                        {"field": "temperature", "parameter": "temperature", "unit": "celsius"},
                        {"field": "pressure", "parameter": "pressure", "unit": "bar"},
                    ],
                }
            ],
            "output": {
                "kafka_bootstrap": "kafka:9092",
                "topic": "telemetry.raw",
                "events_topic": "events.raw",
                "asset_id": "line1_sensor_pack",
            },
        }

    def _event_config(self) -> dict:
        return {
            "broker_host": "mqtt-broker",
            "broker_port": 1883,
            "client_id": "streamforge-mqtt-events",
            "qos": 1,
            "subscriptions": [
                {
                    "topic": "factory/line1/events",
                    "payload_format": "json",
                    "message_type": "event",
                    "asset_id": "line1_sensor_pack",
                    "mappings": [],
                }
            ],
            "output": {
                "kafka_bootstrap": "kafka:9092",
                "topic": "telemetry.raw",
                "events_topic": "events.raw",
                "asset_id": "line1_sensor_pack",
            },
        }

    def test_ingest_telemetry_json_maps_to_normalized_readings(self) -> None:
        adapter = MqttAdapter(self._telemetry_config())

        adapter._ingest_message(
            "factory/line1/telemetry",
            json.dumps({"temperature": 78.5, "pressure": 12, "device_time": "2026-05-15T10:00:00Z"}).encode("utf-8"),
        )

        raw = adapter.poll()
        message = adapter.transform(raw)

        self.assertEqual(message["telemetry"]["asset_id"], "line1_sensor_pack")
        self.assertEqual(len(message["telemetry"]["readings"]), 2)
        self.assertEqual(message["telemetry"]["readings"][0]["parameter"], "temperature")
        self.assertEqual(message["telemetry"]["readings"][0]["value"], 78.5)
        self.assertEqual(message["telemetry"]["readings"][1]["parameter"], "pressure")
        self.assertEqual(message["events"], [])

    def test_ingest_event_json_maps_to_normalized_event(self) -> None:
        adapter = MqttAdapter(self._event_config())

        adapter._ingest_message(
            "factory/line1/events",
            json.dumps(
                {
                    "event_type": "motor_state_change",
                    "previous_state": {"motor_running": False},
                    "new_state": {"motor_running": True},
                    "device_time": "2026-05-15T10:00:00Z",
                }
            ).encode("utf-8"),
        )

        raw = adapter.poll()
        message = adapter.transform(raw)

        self.assertEqual(message["telemetry"], None)
        self.assertEqual(len(message["events"]), 1)
        self.assertEqual(message["events"][0]["event_type"], "motor_state_change")
        self.assertEqual(message["events"][0]["new_state"]["motor_running"], True)

    def test_invalid_json_increments_parse_failures(self) -> None:
        adapter = MqttAdapter(self._telemetry_config())

        adapter._ingest_message("factory/line1/telemetry", b"{bad json")

        health = adapter.health()
        self.assertEqual(health["parse_failures"], 1)
        self.assertEqual(health["parsed_messages"], 0)

    def test_unsupported_payload_format_marks_adapter_degraded(self) -> None:
        config = self._telemetry_config()
        config["subscriptions"][0]["payload_format"] = "csv"
        adapter = MqttAdapter(config)

        adapter._ingest_message("factory/line1/telemetry", b"temperature,78.5")

        health = adapter.health()
        self.assertEqual(health["status"], "degraded")
        self.assertEqual(health["parse_failures"], 1)
        self.assertIn("Unsupported MQTT payload_format", str(health["last_error"]))

    def test_unmatched_topic_is_counted_as_ignored(self) -> None:
        adapter = MqttAdapter(self._telemetry_config())

        adapter._ingest_message("factory/line1/unknown", b"{}")

        health = adapter.health()
        self.assertEqual(health["ignored_messages"], 1)
        self.assertEqual(health["parsed_messages"], 0)

    def test_on_connect_subscribes_to_topics(self) -> None:
        adapter = MqttAdapter(self._telemetry_config())
        client = FakeMqttClient()
        event = FakeEvent()
        adapter._connected_event = event

        adapter._on_connect(client, None, None, 0)

        self.assertTrue(event.set_called)
        self.assertEqual(client.subscriptions, [("factory/line1/telemetry", 1)])

    def test_connect_configures_credentials_and_starts_loop(self) -> None:
        config = self._telemetry_config()
        config["username"] = "demo"
        config["password"] = "secret"
        adapter = MqttAdapter(config)
        client = FakeMqttClient()
        event = FakeEvent()
        event.set()

        adapter._create_client = lambda client_id: client  # type: ignore[method-assign]
        adapter._event_factory = lambda: event  # type: ignore[method-assign]

        adapter.connect()

        self.assertEqual(client.username, "demo")
        self.assertEqual(client.password, "secret")
        self.assertEqual(client.connect_args, ("mqtt-broker", 1883, 60))
        self.assertTrue(client.loop_started)


if __name__ == "__main__":
    unittest.main()
