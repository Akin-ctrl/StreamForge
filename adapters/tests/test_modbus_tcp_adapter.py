"""Tests for Modbus register batching behavior."""

from __future__ import annotations

import unittest

from adapters.adapter_modbus_tcp.modbus_tcp_adapter import CoilSpec, ModbusTcpAdapter, RegisterSpec


class FakeResponse:
    """Minimal Modbus response stub."""

    def __init__(self, registers: list[int] | None = None, error: bool = False, bits: list[bool] | None = None) -> None:
        self.registers = registers
        self.bits = bits or []
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
        self.coil_calls: list[tuple[int, int, int]] = []

    def connect(self) -> bool:
        return self.connect_result

    def close(self) -> None:
        self.closed = True

    def read_holding_registers(self, address: int, count: int, device_id: int):
        call = (address, count, device_id)
        self.calls.append(call)
        return self.responses[call]

    def read_input_registers(self, address: int, count: int, device_id: int):
        call = (address, count, device_id)
        self.calls.append(call)
        return self.responses[call]

    def read_coils(self, address: int, count: int, device_id: int):
        call = (address, count, device_id)
        self.coil_calls.append(call)
        return self.responses[call]

    def read_discrete_inputs(self, address: int, count: int, device_id: int):
        call = (address, count, device_id)
        self.coil_calls.append(call)
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
                "coils": [],
                "output": {
                    "kafka_bootstrap": "localhost:9092",
                    "topic": "telemetry.raw",
                    "events_topic": "events.raw",
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
        self.assertEqual(readings["readings"]["speed"]["value"], 120)
        self.assertEqual(readings["readings"]["amps"]["value"], 153)
        self.assertEqual(readings["readings"]["temperature"]["value"], 100.0)
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
        self.assertEqual(readings["readings"]["speed"]["value"], 120)
        self.assertEqual(readings["readings"]["count"]["value"], 48291)
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
        self.assertEqual(readings["readings"]["speed"]["value"], 120)
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

    def test_poll_reads_coils_and_emits_state_change_events(self) -> None:
        adapter = self._adapter(
            [
                {"address": 40001, "param": "speed", "type": "uint16", "unit": "m/min"},
            ]
        )
        adapter.config["coils"] = [
            {"address": 1, "param": "motor_running", "event_type": "motor_state_change"},
            {"address": 2, "param": "faulted", "event_type": "fault_state_change"},
        ]
        adapter._client = FakeClient(
            {
                (0, 1, 1): FakeResponse([120]),
                (0, 2, 1): FakeResponse(bits=[False, False]),
            }
        )

        first = adapter.poll()
        self.assertEqual(first["events"], [])
        self.assertEqual(adapter._client.coil_calls, [(0, 2, 1)])

        adapter._client = FakeClient(
            {
                (0, 1, 1): FakeResponse([120]),
                (0, 2, 1): FakeResponse(bits=[True, False]),
            }
        )

        second = adapter.poll()
        transformed = adapter.transform(second)

        self.assertEqual(len(second["events"]), 1)
        self.assertEqual(second["events"][0]["event_type"], "motor_state_change")
        self.assertEqual(transformed["events"][0]["previous_state"]["motor_running"], False)
        self.assertEqual(transformed["events"][0]["new_state"]["motor_running"], True)
        self.assertEqual(transformed["events"][0]["classification"], "EVENT")

    def test_poll_reads_canonical_points_for_registers_and_events(self) -> None:
        adapter = ModbusTcpAdapter(
            {
                "host": "127.0.0.1",
                "port": 502,
                "unit_id": 1,
                "points": [
                    {
                        "point_name": "temperature",
                        "memory_area": "holding_register",
                        "address": 40001,
                        "data_type": "float32",
                        "unit": "celsius",
                        "classification": "telemetry",
                    },
                    {
                        "point_name": "motor_running",
                        "memory_area": "coil",
                        "address": 1,
                        "data_type": "bool",
                        "classification": "event",
                        "event_type": "motor_state_change",
                    },
                ],
                "output": {
                    "kafka_bootstrap": "localhost:9092",
                    "topic": "telemetry.raw",
                    "events_topic": "events.raw",
                    "asset_id": "asset-1",
                },
            }
        )
        adapter._client = FakeClient(
            {
                (0, 2, 1): FakeResponse([0x42C8, 0x0000]),
                (0, 1, 1): FakeResponse(bits=[False]),
            }
        )

        first = adapter.poll()
        self.assertEqual(first["readings"]["temperature"]["value"], 100.0)
        self.assertEqual(first["events"], [])

        adapter._client = FakeClient(
            {
                (0, 2, 1): FakeResponse([0x42C8, 0x0000]),
                (0, 1, 1): FakeResponse(bits=[True]),
            }
        )
        second = adapter.poll()

        self.assertEqual(len(second["events"]), 1)
        self.assertEqual(second["events"][0]["event_type"], "motor_state_change")

    def test_poll_reads_input_registers_and_discrete_inputs_from_canonical_points(self) -> None:
        adapter = ModbusTcpAdapter(
            {
                "host": "127.0.0.1",
                "port": 502,
                "unit_id": 1,
                "points": [
                    {
                        "point_name": "line_pressure",
                        "memory_area": "input_register",
                        "address": 30001,
                        "data_type": "uint16",
                        "unit": "bar",
                        "classification": "telemetry",
                    },
                    {
                        "point_name": "door_open",
                        "memory_area": "discrete_input",
                        "address": 10001,
                        "data_type": "bool",
                        "unit": "",
                        "classification": "telemetry",
                    },
                ],
                "output": {
                    "kafka_bootstrap": "localhost:9092",
                    "topic": "telemetry.raw",
                    "events_topic": "events.raw",
                    "asset_id": "asset-1",
                },
            }
        )
        adapter._client = FakeClient({})

        def read_input_registers(address: int, count: int, device_id: int):
            call = (address, count, device_id)
            adapter._client.calls.append(call)
            return FakeResponse([7])

        def read_discrete_inputs(address: int, count: int, device_id: int):
            call = (address, count, device_id)
            adapter._client.coil_calls.append(call)
            return FakeResponse(bits=[True])

        adapter._client.read_input_registers = read_input_registers  # type: ignore[method-assign]
        adapter._client.read_discrete_inputs = read_discrete_inputs  # type: ignore[method-assign]

        polled = adapter.poll()

        self.assertEqual(adapter._client.calls, [(0, 1, 1)])
        self.assertEqual(adapter._client.coil_calls, [(0, 1, 1)])
        self.assertEqual(polled["readings"]["line_pressure"]["value"], 7)
        self.assertEqual(polled["readings"]["door_open"]["value"], True)

    def test_build_coil_batches_groups_contiguous_specs(self) -> None:
        specs = [
            CoilSpec(address=0, param="motor_running", event_type="motor_state_change"),
            CoilSpec(address=1, param="faulted", event_type="fault_state_change"),
            CoilSpec(address=4, param="ready", event_type="ready_state_change"),
        ]

        batches = ModbusTcpAdapter._build_coil_batches(specs)

        self.assertEqual(len(batches), 2)
        self.assertEqual((batches[0].start, batches[0].count), (0, 2))
        self.assertEqual((batches[1].start, batches[1].count), (4, 1))


if __name__ == "__main__":
    unittest.main()
