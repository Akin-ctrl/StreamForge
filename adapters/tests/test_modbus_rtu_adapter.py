"""Tests for the Modbus RTU adapter transport configuration."""

from __future__ import annotations

import unittest

from adapters.adapter_modbus_rtu.modbus_rtu_adapter import ModbusRtuAdapter


class FakeSerialClient:
    def __init__(self, connect_result: bool = True) -> None:
        self.connect_result = connect_result
        self.closed = False

    def connect(self) -> bool:
        return self.connect_result

    def close(self) -> None:
        self.closed = True


class ModbusRtuAdapterTests(unittest.TestCase):
    def _adapter(self) -> ModbusRtuAdapter:
        return ModbusRtuAdapter(
            {
                "port": "/dev/ttyUSB0",
                "baudrate": 19200,
                "bytesize": 8,
                "parity": "E",
                "stopbits": 1,
                "timeout": 1.5,
                "unit_id": 1,
                "poll_interval_ms": 1000,
                "registers": [],
                "coils": [],
                "output": {
                    "kafka_bootstrap": "localhost:9092",
                    "topic": "telemetry.raw",
                    "events_topic": "events.raw",
                    "asset_id": "asset-1",
                },
            }
        )

    def test_connect_uses_serial_transport_config(self) -> None:
        adapter = self._adapter()
        captured: dict[str, object] = {}
        fake_client = FakeSerialClient(connect_result=True)

        def create_serial_client(**kwargs):
            captured.update(kwargs)
            return fake_client

        adapter._create_serial_client = create_serial_client  # type: ignore[method-assign]

        adapter.connect()

        self.assertIs(adapter._client, fake_client)
        self.assertEqual(captured["port"], "/dev/ttyUSB0")
        self.assertEqual(captured["baudrate"], 19200)
        self.assertEqual(captured["parity"], "E")
        self.assertEqual(captured["timeout"], 1.5)

    def test_connect_requires_serial_port(self) -> None:
        adapter = self._adapter()
        adapter.config["port"] = ""
        adapter.config["device"] = ""

        with self.assertRaisesRegex(RuntimeError, "requires 'port' or 'device'"):
            adapter.connect()

    def test_health_exposes_transport_metadata(self) -> None:
        adapter = self._adapter()

        health = adapter.health()

        self.assertEqual(health["transport"], "rtu")
        self.assertEqual(health["serial_port"], "/dev/ttyUSB0")
        self.assertEqual(health["baudrate"], 19200)


if __name__ == "__main__":
    unittest.main()
