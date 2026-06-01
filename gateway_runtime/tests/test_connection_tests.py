"""Gateway-side connection test probes."""

from __future__ import annotations

from contextlib import nullcontext
import unittest
from unittest.mock import patch

from gateway_runtime.connection_tests import run_gateway_connection_test


class GatewayConnectionProbeTests(unittest.TestCase):
    def test_mqtt_probe_uses_gateway_network_tcp_reachability(self) -> None:
        seen: list[tuple[str, int]] = []

        def fake_create_connection(address: tuple[str, int], timeout: int) -> object:
            seen.append(address)
            return nullcontext()

        with patch("gateway_runtime.connection_tests.create_connection", fake_create_connection):
            result = run_gateway_connection_test(
                "adapter",
                "mqtt",
                {"broker_host": "mqtt.local", "broker_port": "1884"},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "passed")
        self.assertEqual(seen, [("mqtt.local", 1884)])

    def test_modbus_rtu_without_serial_port_is_gateway_unsupported(self) -> None:
        result = run_gateway_connection_test("adapter", "modbus_rtu", {})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "cannot_test_from_gateway")
        self.assertEqual(result["probes"][0]["status"], "unsupported")

    def test_unknown_target_kind_is_unsupported(self) -> None:
        result = run_gateway_connection_test("unknown", "thing", {})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "cannot_test_from_gateway")


if __name__ == "__main__":
    unittest.main()
