"""Tests for the OPC UA adapter mapping behavior."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from adapters.adapter_opcua.opcua_adapter import OpcUaAdapter


class FakeNode:
    def __init__(self, node_id: str) -> None:
        self.nodeid = node_id


class FakeSubscription:
    def __init__(self, handler) -> None:
        self.handler = handler
        self.handles: list[str] = []
        self.unsubscribed = None
        self.deleted = False

    def subscribe_data_change(self, node) -> str:
        handle = f"handle:{node.nodeid}"
        self.handles.append(handle)
        return handle

    def unsubscribe(self, handles) -> None:
        self.unsubscribed = handles

    def delete(self) -> None:
        self.deleted = True


class FakeOpcUaClient:
    def __init__(self) -> None:
        self.username = None
        self.password = None
        self.connected = False
        self.endpoint = None
        self.subscription = None

    def set_user(self, username: str) -> None:
        self.username = username

    def set_password(self, password: str) -> None:
        self.password = password

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def create_subscription(self, interval_ms: int, handler) -> FakeSubscription:
        self.subscription = FakeSubscription(handler)
        return self.subscription

    def get_node(self, node_id: str) -> FakeNode:
        return FakeNode(node_id)


class FakeDataChange:
    def __init__(self, source_timestamp: datetime | None = None) -> None:
        self.source_timestamp = source_timestamp


class OpcUaAdapterTests(unittest.TestCase):
    def _config(self) -> dict:
        return {
            "endpoint": "opc.tcp://opcua-server:4840",
            "security_mode": "None",
            "security_policy": "None",
            "username": "demo",
            "password": "secret",
            "subscription_interval_ms": 1000,
            "monitored_items": [
                {
                    "node_id": "ns=2;s=Line1.Temperature",
                    "parameter": "temperature",
                    "unit": "celsius",
                    "asset_id": "line1",
                }
            ],
            "output": {
                "kafka_bootstrap": "kafka:9092",
                "topic": "telemetry.raw",
                "events_topic": "events.raw",
                "asset_id": "line1",
            },
        }

    def test_connect_creates_subscription_and_monitored_items(self) -> None:
        adapter = OpcUaAdapter(self._config())
        client = FakeOpcUaClient()
        adapter._create_client = lambda endpoint: client  # type: ignore[method-assign]

        adapter.connect()

        self.assertTrue(client.connected)
        self.assertEqual(client.username, "demo")
        self.assertEqual(client.password, "secret")
        self.assertEqual(client.subscription.handles, ["handle:ns=2;s=Line1.Temperature"])

    def test_disconnect_unsubscribes_monitored_items_and_clears_connection(self) -> None:
        adapter = OpcUaAdapter(self._config())
        client = FakeOpcUaClient()
        adapter._create_client = lambda endpoint: client  # type: ignore[method-assign]

        adapter.connect()
        adapter.disconnect()

        self.assertFalse(client.connected)
        self.assertEqual(client.subscription.unsubscribed, ["handle:ns=2;s=Line1.Temperature"])
        self.assertTrue(client.subscription.deleted)
        self.assertEqual(adapter.health()["connected"], False)

    def test_datachange_maps_to_normalized_telemetry(self) -> None:
        adapter = OpcUaAdapter(self._config())
        adapter._ingest_datachange(
            FakeNode("ns=2;s=Line1.Temperature"),
            78.5,
            FakeDataChange(source_timestamp=datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc)),
        )

        raw = adapter.poll()
        message = adapter.transform(raw)

        self.assertEqual(message["asset_id"], "line1")
        self.assertEqual(message["readings"][0]["parameter"], "temperature")
        self.assertEqual(message["readings"][0]["value"], 78.5)
        self.assertEqual(message["readings"][0]["device_time"], "2026-05-15T10:00:00+00:00")

    def test_unmapped_node_increments_parse_failures(self) -> None:
        adapter = OpcUaAdapter(self._config())
        adapter._ingest_datachange(FakeNode("ns=2;s=Line1.Unknown"), 1, FakeDataChange())

        health = adapter.health()
        self.assertEqual(health["parse_failures"], 1)
        self.assertIn("Unmapped OPC UA node", str(health["last_error"]))

    def test_non_none_security_mode_is_rejected_in_v1(self) -> None:
        config = self._config()
        config["security_mode"] = "Sign"
        adapter = OpcUaAdapter(config)

        with self.assertRaisesRegex(RuntimeError, "supports only security_mode=None"):
            adapter.connect()

    def test_requires_at_least_one_monitored_item(self) -> None:
        config = self._config()
        config["monitored_items"] = []

        with self.assertRaisesRegex(RuntimeError, "requires at least one monitored_item"):
            OpcUaAdapter(config)


if __name__ == "__main__":
    unittest.main()
