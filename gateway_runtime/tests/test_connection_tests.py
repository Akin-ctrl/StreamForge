"""Gateway-side connection test probes."""

from __future__ import annotations

from contextlib import nullcontext
from types import ModuleType
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

    def test_modbus_rtu_framed_tcp_endpoint_uses_gateway_network_probe(self) -> None:
        seen: list[tuple[str, int]] = []

        def fake_create_connection(address: tuple[str, int], timeout: int) -> object:
            seen.append(address)
            return nullcontext()

        with patch("gateway_runtime.connection_tests.create_connection", fake_create_connection):
            result = run_gateway_connection_test(
                "adapter",
                "modbus_rtu",
                {"serial_port": "rtu://plant-simulator:16020"},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "passed")
        self.assertEqual(seen, [("plant-simulator", 16020)])

    def test_unreachable_modbus_tcp_returns_failed_probe(self) -> None:
        instances: list[FakeModbusTcpClient] = []

        class FakeModbusTcpClient:
            def __init__(self, *, host: str, port: int, timeout: int) -> None:
                self.host = host
                self.port = port
                self.timeout = timeout
                self.closed = False
                instances.append(self)

            def connect(self) -> bool:
                return False

            def close(self) -> None:
                self.closed = True

        pymodbus_module = ModuleType("pymodbus")
        client_module = ModuleType("pymodbus.client")
        client_module.ModbusTcpClient = FakeModbusTcpClient

        with patch.dict("sys.modules", {"pymodbus": pymodbus_module, "pymodbus.client": client_module}):
            result = run_gateway_connection_test("adapter", "modbus_tcp", {"host": "plc.local", "port": 1502})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("plc.local:1502", result["message"])
        self.assertEqual(result["probes"][0]["status"], "failed")
        self.assertEqual((instances[0].host, instances[0].port, instances[0].timeout), ("plc.local", 1502, 3))
        self.assertTrue(instances[0].closed)

    def test_modbus_tcp_without_client_is_gateway_unsupported(self) -> None:
        with patch.dict("sys.modules", {"pymodbus": None, "pymodbus.client": None}):
            result = run_gateway_connection_test("adapter", "modbus_tcp", {"host": "plc.local", "port": 502})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "cannot_test_from_gateway")
        self.assertEqual(result["probes"][0]["status"], "unsupported")

    def test_unreachable_timescaledb_returns_failed_probe(self) -> None:
        class FakePsycopgError(Exception):
            pass

        def fake_connect(dsn: str, connect_timeout: int) -> object:
            self.assertEqual(dsn, "postgresql://sf_user:sf_password@timescaledb:5432/streamforge")
            self.assertEqual(connect_timeout, 3)
            raise FakePsycopgError("connection refused")

        psycopg_module = ModuleType("psycopg")
        psycopg_module.Error = FakePsycopgError
        psycopg_module.connect = fake_connect

        with patch.dict("sys.modules", {"psycopg": psycopg_module}):
            result = run_gateway_connection_test(
                "sink",
                "timescaledb",
                {"db_dsn": "postgresql://sf_user:sf_password@timescaledb:5432/streamforge"},
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("TimescaleDB connectivity check from gateway failed", result["message"])
        self.assertEqual(result["probes"][0]["status"], "failed")
        self.assertIn("connection refused", result["probes"][0]["message"])

    def test_unknown_adapter_type_is_gateway_unsupported(self) -> None:
        result = run_gateway_connection_test("adapter", "ethernet_ip", {})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "cannot_test_from_gateway")
        self.assertEqual(result["probes"][0]["status"], "unsupported")

    def test_unknown_sink_type_is_gateway_unsupported(self) -> None:
        result = run_gateway_connection_test("sink", "s3", {})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "cannot_test_from_gateway")
        self.assertEqual(result["probes"][0]["status"], "unsupported")

    def test_unknown_target_kind_is_unsupported(self) -> None:
        result = run_gateway_connection_test("unknown", "thing", {})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "cannot_test_from_gateway")


if __name__ == "__main__":
    unittest.main()
