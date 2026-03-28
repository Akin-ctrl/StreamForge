"""Modbus TCP adapter implementation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from struct import unpack
from typing import Dict, Iterable, Sequence

from adapters.adapter_base.base_adapter import BaseAdapter


@dataclass(frozen=True)
class RegisterSpec:
    """Single Modbus register specification."""

    address: int
    param: str
    data_type: str
    unit: str


@dataclass(frozen=True)
class RegisterBatch:
    """A contiguous or overlapping block of Modbus registers to read together."""

    start: int
    count: int
    specs: tuple[RegisterSpec, ...]


class ModbusTcpAdapter(BaseAdapter):
    """
    Modbus TCP adapter implementation.

    Overrides BaseAdapter hooks for Modbus protocol.
    """

    def __init__(self, config: dict) -> None:
        """Initialize adapter with validated config."""
        super().__init__(config)
        self._client = None
        self._connect_max_attempts = max(int(config.get("connect_max_attempts", 3)), 1)
        self._read_max_attempts = max(int(config.get("read_max_attempts", 3)), 1)
        self._retry_backoff_s = max(float(config.get("retry_backoff_ms", 250)) / 1000.0, 0.0)
        self._retry_backoff_multiplier = max(float(config.get("retry_backoff_multiplier", 2.0)), 1.0)
        self._retry_max_backoff_s = max(
            float(config.get("retry_max_backoff_ms", 5000)) / 1000.0,
            self._retry_backoff_s,
        )
        self._health.update(
            {
                "modbus_connect_failures": 0,
                "modbus_read_failures": 0,
                "modbus_reconnects": 0,
                "last_modbus_error": None,
                "last_modbus_retry_operation": None,
                "last_modbus_retry_attempt": 0,
                "last_modbus_backoff_s": 0.0,
            }
        )

    def connect(self) -> None:
        """Connect to Modbus TCP server."""
        host = self.config["host"]
        port = int(self.config.get("port", 502))

        def attempt() -> None:
            self.disconnect()
            client = self._create_client(host=host, port=port)
            if not client.connect():
                raise RuntimeError(f"Unable to connect to Modbus server {host}:{port}")
            self._client = client
            self._health["connected"] = True

        self._retry_operation(
            operation="connect",
            max_attempts=self._connect_max_attempts,
            action=attempt,
        )

    def disconnect(self) -> None:
        """Close protocol and Kafka resources during graceful shutdown."""
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None
        self._health["connected"] = False

    def poll(self) -> Dict[str, object]:
        """Poll configured registers."""
        if self._client is None:
            self.connect()

        unit_id = int(self.config.get("unit_id", 1))
        registers = sorted(self._iter_registers(), key=lambda spec: spec.address)
        batches = self._build_batches(registers)
        readings: Dict[str, object] = {}

        self._health["last_modbus_batch_count"] = len(batches)
        self._health["last_modbus_register_span"] = sum(batch.count for batch in batches)

        for batch in batches:
            response = self._read_batch_with_retry(batch=batch, unit_id=unit_id)

            for spec in batch.specs:
                start_index = spec.address - batch.start
                end_index = start_index + self._register_width(spec)
                value = self._decode_value(spec, response.registers[start_index:end_index])
                readings[spec.param] = {"value": value, "unit": spec.unit}

        return readings

    def transform(self, raw: Dict[str, object]) -> Dict[str, object]:
        """Map registers to telemetry message."""
        now = datetime.now(timezone.utc).isoformat()
        output = self.config["output"]
        asset_id = output["asset_id"]

        messages: Dict[str, object] = {
            "asset_id": asset_id,
            "gateway_time": now,
            "readings": [],
        }

        for param, payload in raw.items():
            messages["readings"].append(
                {
                    "parameter": param,
                    "value": payload["value"],
                    "unit": payload["unit"],
                    "quality": "GOOD",
                    "device_time": None,
                }
            )

        return messages

    def _iter_registers(self) -> Iterable[RegisterSpec]:
        """Yield register specs from configuration."""
        for item in self.config.get("registers", []):
            address = self._normalize_address(int(item["address"]))
            yield RegisterSpec(
                address=address,
                param=item["param"],
                data_type=item.get("type", "uint16"),
                unit=item.get("unit", "")
            )

    def _read_batch_with_retry(self, batch: RegisterBatch, unit_id: int):
        """Read a batch with reconnect-aware retry semantics."""

        def attempt():
            if self._client is None:
                raise RuntimeError("Modbus client not connected")
            response = self._client.read_holding_registers(
                batch.start,
                count=batch.count,
                device_id=unit_id,
            )
            if response.isError():
                raise RuntimeError(f"Modbus read error at {batch.start}")
            return response

        return self._retry_operation(
            operation="read",
            max_attempts=self._read_max_attempts,
            action=attempt,
            before_retry=self._reconnect_after_read_failure,
        )

    def _reconnect_after_read_failure(self) -> None:
        """Reconnect the Modbus client before retrying a failed read."""
        self._health["modbus_reconnects"] = int(self._health["modbus_reconnects"]) + 1
        self.disconnect()
        self.connect()

    def _retry_operation(self, operation: str, max_attempts: int, action, before_retry=None):
        """Run an operation with bounded exponential backoff."""
        delay_s = self._retry_backoff_s

        for attempt in range(1, max_attempts + 1):
            try:
                return action()
            except Exception as exc:
                self._record_modbus_failure(operation=operation, attempt=attempt, exc=exc)
                if attempt >= max_attempts:
                    raise
                self._set_status(
                    "degraded",
                    running=bool(self._health.get("running")),
                    last_error=str(exc),
                )
                self._health["last_modbus_backoff_s"] = delay_s
                self._sleep(delay_s)
                if before_retry is not None:
                    before_retry()
                delay_s = min(delay_s * self._retry_backoff_multiplier, self._retry_max_backoff_s)

        raise RuntimeError(f"Unreachable retry state for {operation}")

    def _record_modbus_failure(self, operation: str, attempt: int, exc: Exception) -> None:
        """Track Modbus retry state in adapter health."""
        counter_key = "modbus_connect_failures" if operation == "connect" else "modbus_read_failures"
        self._health[counter_key] = int(self._health[counter_key]) + 1
        self._health["last_modbus_error"] = str(exc)
        self._health["last_modbus_retry_operation"] = operation
        self._health["last_modbus_retry_attempt"] = attempt
        self._health["last_error"] = str(exc)

    @classmethod
    def _build_batches(cls, specs: Sequence[RegisterSpec]) -> list[RegisterBatch]:
        """Group contiguous or overlapping register specs into shared reads."""
        if not specs:
            return []

        batches: list[RegisterBatch] = []
        current_start = specs[0].address
        current_end = current_start + cls._register_width(specs[0])
        current_specs = [specs[0]]

        for spec in specs[1:]:
            spec_end = spec.address + cls._register_width(spec)
            if spec.address <= current_end:
                current_end = max(current_end, spec_end)
                current_specs.append(spec)
                continue

            batches.append(
                RegisterBatch(
                    start=current_start,
                    count=current_end - current_start,
                    specs=tuple(current_specs),
                )
            )
            current_start = spec.address
            current_end = spec_end
            current_specs = [spec]

        batches.append(
            RegisterBatch(
                start=current_start,
                count=current_end - current_start,
                specs=tuple(current_specs),
            )
        )
        return batches

    @classmethod
    def _register_width(cls, spec: RegisterSpec) -> int:
        """Return the number of 16-bit registers needed for a spec."""
        if spec.data_type == "float32":
            return 2
        return 1

    @classmethod
    def _decode_value(cls, spec: RegisterSpec, registers: Sequence[int]) -> float | int:
        """Decode register values based on the configured data type."""
        if spec.data_type == "float32":
            if len(registers) != 2:
                raise RuntimeError(f"Expected 2 registers for float32 at {spec.address}")
            return cls._decode_float32(list(registers))
        if not registers:
            raise RuntimeError(f"Missing register data at {spec.address}")
        return int(registers[0])

    @staticmethod
    def _normalize_address(address: int) -> int:
        """Normalize Modbus address to zero-based register offset."""
        if address >= 40001:
            return address - 40001
        return address

    @staticmethod
    def _decode_float32(registers: list[int]) -> float:
        """Decode two 16-bit registers into IEEE754 float32."""
        packed = bytes([registers[0] >> 8, registers[0] & 0xFF, registers[1] >> 8, registers[1] & 0xFF])
        return unpack(">f", packed)[0]

    @staticmethod
    def _sleep(seconds: float) -> None:
        """Pause between retries."""
        time.sleep(seconds)

    @staticmethod
    def _create_client(host: str, port: int):
        """Construct a Modbus TCP client."""
        try:
            from pymodbus.client import ModbusTcpClient  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("pymodbus is required for ModbusTcpAdapter") from exc

        return ModbusTcpClient(host=host, port=port)
