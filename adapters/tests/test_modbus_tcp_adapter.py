"""Tests for Modbus register batching behavior."""

from __future__ import annotations

import unittest

from adapters.adapter_modbus_tcp.modbus_tcp_adapter import ModbusTcpAdapter, RegisterSpec


class FakeResponse:
    """Minimal Modbus response stub."""

    def __init__(self, registers: list[int], error: bool = False) -> None:
        self.registers = registers
        self._error = error

    def isError(self) -> bool:
        return self._error


class FakeClient:
    """Modbus client stub that records reads."""

    def __init__(
        self,
        responses: dict[tuple[int, int, int], FakeResponse] | None = None,
        connect_result: bool = True,
    ) -> None:
        self.responses = responses or {}
        self.connect_result = connect_result
        self.closed = False
        self.calls: list[tuple[int, int, int]] = []

    def connect(self) -> bool:
        return self.connect_result

    def close(self) -> None:
        self.closed = True

    def read_holding_registers(self, address: int, count: int, device_id: int):
        call = (address, count, device_id)
        self.calls.append(call)
        return self.responses[call]


class ModbusTcpAdapterBatchingTests(unittest.TestCase):
    def _adapter(self, registers: list[dict[str, object]]) -> ModbusTcpAdapter:
        adapter = ModbusTcpAdapter(
            {
                "host": "127.0.0.1",
                "port": 502,
                "unit_id": 1,
                "connect_max_attempts": 3,
                "read_max_attempts": 3,
                "retry_backoff_ms": 1,
                "retry_backoff_multiplier": 2.0,
                "retry_max_backoff_ms": 5,
                "registers": registers,
                "output": {
                    "kafka_bootstrap": "localhost:9092",
                    "topic": "telemetry.raw",
                    "asset_id": "asset-1",
                },
            }
        )
        return adapter

    def test_build_batches_groups_contiguous_and_overlapping_specs(self) -> None:
        specs = [
            RegisterSpec(address=0, param="speed", data_type="uint16", unit="m/min"),
            RegisterSpec(address=1, param="amps", data_type="uint16", unit="amps"),
            RegisterSpec(address=2, param="temperature", data_type="float32", unit="celsius"),
            RegisterSpec(address=6, param="count", data_type="uint16", unit="count"),
        ]

        batches = ModbusTcpAdapter._build_batches(specs)

        self.assertEqual(len(batches), 2)
        self.assertEqual((batches[0].start, batches[0].count), (0, 4))
        self.assertEqual((batches[1].start, batches[1].count), (6, 1))

    def test_poll_reads_contiguous_block_once_and_decodes_values(self) -> None:
        adapter = self._adapter(
            [
                {"address": 40001, "param": "speed", "type": "uint16", "unit": "m/min"},
                {"address": 40002, "param": "amps", "type": "uint16", "unit": "amps"},
                {"address": 40003, "param": "temperature", "type": "float32", "unit": "celsius"},
            ]
        )
        adapter._client = FakeClient(
            {
                (0, 4, 1): FakeResponse([120, 153, 0x42C8, 0x0000]),
            }
        )

        readings = adapter.poll()

        self.assertEqual(adapter._client.calls, [(0, 4, 1)])
        self.assertEqual(readings["speed"]["value"], 120)
        self.assertEqual(readings["amps"]["value"], 153)
        self.assertEqual(readings["temperature"]["value"], 100.0)
        self.assertEqual(adapter.health()["last_modbus_batch_count"], 1)
        self.assertEqual(adapter.health()["last_modbus_register_span"], 4)

    def test_poll_splits_non_contiguous_blocks(self) -> None:
        adapter = self._adapter(
            [
                {"address": 40001, "param": "speed", "type": "uint16", "unit": "m/min"},
                {"address": 40005, "param": "count", "type": "uint16", "unit": "count"},
            ]
        )
        adapter._client = FakeClient(
            {
                (0, 1, 1): FakeResponse([120]),
                (4, 1, 1): FakeResponse([48291]),
            }
        )

        readings = adapter.poll()

        self.assertEqual(adapter._client.calls, [(0, 1, 1), (4, 1, 1)])
        self.assertEqual(readings["speed"]["value"], 120)
        self.assertEqual(readings["count"]["value"], 48291)
        self.assertEqual(adapter.health()["last_modbus_batch_count"], 2)
        self.assertEqual(adapter.health()["last_modbus_register_span"], 2)

    def test_connect_retries_with_backoff_until_success(self) -> None:
        adapter = self._adapter([])
        first_client = FakeClient(connect_result=False)
        second_client = FakeClient(connect_result=True)
        clients = iter([first_client, second_client])
        sleep_calls: list[float] = []

        adapter._create_client = lambda host, port: next(clients)  # type: ignore[method-assign]
        adapter._sleep = lambda seconds: sleep_calls.append(seconds)  # type: ignore[method-assign]

        adapter.connect()

        self.assertIs(adapter._client, second_client)
        self.assertEqual(sleep_calls, [0.001])
        health = adapter.health()
        self.assertEqual(health["modbus_connect_failures"], 1)
        self.assertEqual(health["last_modbus_retry_operation"], "connect")
        self.assertEqual(health["last_modbus_retry_attempt"], 1)

    def test_poll_retries_failed_read_after_reconnect(self) -> None:
        adapter = self._adapter(
            [
                {"address": 40001, "param": "speed", "type": "uint16", "unit": "m/min"},
            ]
        )
        initial_client = FakeClient({(0, 1, 1): FakeResponse([], error=True)})
        recovered_client = FakeClient({(0, 1, 1): FakeResponse([120])})
        sleep_calls: list[float] = []

        adapter._client = initial_client
        adapter._create_client = lambda host, port: recovered_client  # type: ignore[method-assign]
        adapter._sleep = lambda seconds: sleep_calls.append(seconds)  # type: ignore[method-assign]

        readings = adapter.poll()

        self.assertTrue(initial_client.closed)
        self.assertEqual(initial_client.calls, [(0, 1, 1)])
        self.assertEqual(recovered_client.calls, [(0, 1, 1)])
        self.assertEqual(readings["speed"]["value"], 120)
        health = adapter.health()
        self.assertEqual(health["modbus_read_failures"], 1)
        self.assertEqual(health["modbus_reconnects"], 1)
        self.assertEqual(health["last_modbus_retry_operation"], "read")
        self.assertEqual(health["last_modbus_retry_attempt"], 1)
        self.assertEqual(sleep_calls, [0.001])

    def test_poll_raises_after_read_retries_are_exhausted(self) -> None:
        adapter = self._adapter(
            [
                {"address": 40001, "param": "speed", "type": "uint16", "unit": "m/min"},
            ]
        )
        initial_client = FakeClient({(0, 1, 1): FakeResponse([], error=True)})
        reconnect_clients = iter(
            [
                FakeClient({(0, 1, 1): FakeResponse([], error=True)}),
                FakeClient({(0, 1, 1): FakeResponse([], error=True)}),
            ]
        )
        sleep_calls: list[float] = []

        adapter._client = initial_client
        adapter._create_client = lambda host, port: next(reconnect_clients)  # type: ignore[method-assign]
        adapter._sleep = lambda seconds: sleep_calls.append(seconds)  # type: ignore[method-assign]

        with self.assertRaisesRegex(RuntimeError, "Modbus read error"):
            adapter.poll()

        health = adapter.health()
        self.assertEqual(health["modbus_read_failures"], 3)
        self.assertEqual(health["modbus_reconnects"], 2)
        self.assertEqual(health["last_modbus_retry_operation"], "read")
        self.assertEqual(health["last_modbus_retry_attempt"], 3)
        self.assertEqual(sleep_calls, [0.001, 0.002])


if __name__ == "__main__":
    unittest.main()
