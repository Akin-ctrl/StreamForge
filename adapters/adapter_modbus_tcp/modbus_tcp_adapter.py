"""Modbus TCP adapter implementation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from struct import unpack
from typing import Callable, Dict, Iterable, Protocol, Sequence, TypeVar

from adapters.adapter_base.base_adapter import BaseAdapter
from adapters.adapter_base.kafka_publisher import KafkaPublisher


_EVENT_SCHEMA_PATH = str(Path(__file__).resolve().parents[2] / "schemas" / "event.avsc")
T = TypeVar("T")


class RegisterReadResponseLike(Protocol):
    """Minimal Modbus register response surface used by the adapter."""

    registers: Sequence[int]

    def isError(self) -> bool: ...


class CoilReadResponseLike(Protocol):
    """Minimal Modbus binary response surface used by the adapter."""

    bits: Sequence[bool]

    def isError(self) -> bool: ...


class ModbusClientLike(Protocol):
    """Minimal Modbus client surface required by the shared polling pipeline."""

    def connect(self) -> bool: ...
    def close(self) -> None: ...
    def read_holding_registers(self, address: int, count: int, device_id: int) -> RegisterReadResponseLike: ...
    def read_input_registers(self, address: int, count: int, device_id: int) -> RegisterReadResponseLike: ...
    def read_coils(self, address: int, count: int, device_id: int) -> CoilReadResponseLike: ...
    def read_discrete_inputs(self, address: int, count: int, device_id: int) -> CoilReadResponseLike: ...


@dataclass(frozen=True)
class RegisterSpec:
    """Single Modbus register specification."""

    address: int
    param: str
    data_type: str
    unit: str
    memory_area: str = "holding_register"
    scale: float = 1.0
    offset: float = 0.0


@dataclass(frozen=True)
class RegisterBatch:
    """A contiguous or overlapping block of Modbus registers to read together."""

    start: int
    count: int
    specs: tuple[RegisterSpec, ...]


@dataclass(frozen=True)
class CoilSpec:
    """Single Modbus coil specification used for event generation."""

    address: int
    param: str
    event_type: str
    memory_area: str = "coil"
    classification: str = "event"
    unit: str = ""


@dataclass(frozen=True)
class CoilBatch:
    """A contiguous block of Modbus coils to read together."""

    start: int
    count: int
    specs: tuple[CoilSpec, ...]


class ModbusTcpAdapter(BaseAdapter):
    """
    Modbus TCP adapter implementation.

    Overrides BaseAdapter hooks for Modbus protocol.
    """

    def __init__(self, config: dict) -> None:
        """Initialize adapter with validated config."""
        super().__init__(config)
        self._client: ModbusClientLike | None = None
        self._event_publisher: KafkaPublisher | None = None
        self._last_coil_states: dict[str, bool] = {}
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
        if self._event_publisher is not None:
            self._event_publisher.close()
        self._health["connected"] = False

    def poll(self) -> Dict[str, object]:
        """Poll configured registers."""
        if self._client is None:
            self.connect()

        unit_id = int(self.config.get("unit_id", 1))
        registers = sorted(self._iter_registers(), key=lambda spec: spec.address)
        batches = self._build_batches(registers)
        readings: Dict[str, object] = {}
        events: list[dict[str, object]] = []

        self._health["last_modbus_batch_count"] = len(batches)
        self._health["last_modbus_register_span"] = sum(batch.count for batch in batches)

        for batch in batches:
            response = self._read_batch_with_retry(batch=batch, unit_id=unit_id)

            for spec in batch.specs:
                start_index = spec.address - batch.start
                end_index = start_index + self._register_width(spec)
                value = self._decode_value(spec, response.registers[start_index:end_index])
                readings[spec.param] = {"value": value, "unit": spec.unit}

        coils = sorted(self._iter_coils(), key=lambda spec: spec.address)
        coil_batches = self._build_coil_batches(coils)
        if coil_batches:
            self._health["last_modbus_coil_batch_count"] = len(coil_batches)
            self._health["last_modbus_coil_span"] = sum(batch.count for batch in coil_batches)
        else:
            self._health["last_modbus_coil_batch_count"] = 0
            self._health["last_modbus_coil_span"] = 0

        for batch in coil_batches:
            response = self._read_coil_batch_with_retry(batch=batch, unit_id=unit_id)
            for spec in batch.specs:
                state = bool(response.bits[spec.address - batch.start])
                if spec.classification != "event":
                    readings[spec.param] = {"value": state, "unit": spec.unit}
                    continue
                previous_state = self._last_coil_states.get(spec.param)
                self._last_coil_states[spec.param] = state
                if previous_state is None or previous_state == state:
                    continue
                events.append(
                    {
                        "parameter": spec.param,
                        "event_type": spec.event_type,
                        "previous_state": previous_state,
                        "new_state": state,
                    }
                )

        return {"readings": readings, "events": events}

    def transform(self, raw: Dict[str, object]) -> Dict[str, object]:
        """Map polled readings and state changes into telemetry and event messages."""
        now = datetime.now(timezone.utc).isoformat()
        output = self.config["output"]
        asset_id = output["asset_id"]
        deployment_id = str(output.get("deployment_id") or asset_id)

        telemetry_message: Dict[str, object] = {
            "asset_id": asset_id,
            "gateway_time": now,
            "readings": [],
        }

        for param, payload in raw.get("readings", {}).items():
            telemetry_message["readings"].append(
                {
                    "parameter": param,
                    "value": payload["value"],
                    "unit": payload["unit"],
                    "quality": "GOOD",
                    "device_time": None,
                }
            )

        event_messages: list[dict[str, object]] = []
        for item in raw.get("events", []):
            if not isinstance(item, dict):
                continue
            event_messages.append(
                {
                    "asset_id": asset_id,
                    "event_type": str(item.get("event_type") or f"{item.get('parameter', 'state')}_state_change"),
                    "classification": "EVENT",
                    "previous_state": {
                        str(item.get("parameter", "state")): bool(item.get("previous_state", False)),
                    },
                    "new_state": {
                        str(item.get("parameter", "state")): bool(item.get("new_state", False)),
                    },
                    "timestamps": {
                        "device_time": None,
                        "gateway_time": now,
                    },
                    "metadata": {
                        "adapter_id": self._adapter_id,
                        "deployment_id": deployment_id,
                    },
                }
            )

        return {
            "telemetry": telemetry_message,
            "events": event_messages,
        }

    def publish(self, message: Dict[str, object]) -> None:
        """Publish telemetry and events on their explicit topics."""
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

    def health(self) -> Dict[str, object]:
        """Return adapter health with combined telemetry and event publishing stats."""
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

    def _iter_registers(self) -> Iterable[RegisterSpec]:
        """Yield register specs from configuration."""
        raw_points = self.config.get("points")
        if isinstance(raw_points, list) and raw_points:
            for item in raw_points:
                if not isinstance(item, dict):
                    continue
                memory_area = str(item.get("memory_area") or "holding_register").strip()
                if memory_area not in {"holding_register", "input_register"}:
                    continue
                param = str(item.get("point_name") or item.get("param") or "").strip()
                if not param:
                    continue
                address = self._normalize_register_address(int(item["address"]), memory_area)
                yield RegisterSpec(
                    address=address,
                    param=param,
                    data_type=str(item.get("data_type") or item.get("type") or "uint16"),
                    unit=str(item.get("unit") or ""),
                    memory_area=memory_area,
                    scale=float(item.get("scale", 1.0) or 1.0),
                    offset=float(item.get("offset", 0.0) or 0.0),
                )
            return

        for item in self.config.get("registers", []):
            address = self._normalize_register_address(int(item["address"]), "holding_register")
            yield RegisterSpec(
                address=address,
                param=item["param"],
                data_type=item.get("type", "uint16"),
                unit=item.get("unit", ""),
            )

    def _iter_coils(self) -> Iterable[CoilSpec]:
        """Yield coil specs from configuration."""
        raw_points = self.config.get("points")
        if isinstance(raw_points, list) and raw_points:
            for item in raw_points:
                if not isinstance(item, dict):
                    continue
                memory_area = str(item.get("memory_area") or "").strip()
                if memory_area not in {"coil", "discrete_input"}:
                    continue
                param = str(item.get("point_name") or item.get("param") or "").strip()
                if not param:
                    continue
                address = self._normalize_binary_address(int(item["address"]), memory_area)
                yield CoilSpec(
                    address=address,
                    param=param,
                    event_type=str(item.get("event_type") or f"{param}_state_change"),
                    memory_area=memory_area,
                    classification=str(item.get("classification") or "event").strip().lower(),
                    unit=str(item.get("unit") or ""),
                )
            return

        raw_coils = self.config.get("coils", [])
        if isinstance(raw_coils, dict):
            items = []
            for address, item in raw_coils.items():
                if not isinstance(item, dict):
                    continue
                normalized = dict(item)
                normalized.setdefault("address", int(address))
                items.append(normalized)
        else:
            items = list(raw_coils) if isinstance(raw_coils, list) else []

        for item in items:
            if not isinstance(item, dict):
                continue
            param = str(item.get("param", "")).strip()
            if not param:
                continue
            address = self._normalize_binary_address(int(item["address"]), "coil")
            yield CoilSpec(
                address=address,
                param=param,
                event_type=str(item.get("event_type") or f"{param}_state_change"),
            )

    def _read_batch_with_retry(self, batch: RegisterBatch, unit_id: int) -> RegisterReadResponseLike:
        """Read a batch with reconnect-aware retry semantics."""

        def attempt() -> RegisterReadResponseLike:
            if self._client is None:
                raise RuntimeError("Modbus client not connected")
            memory_area = batch.specs[0].memory_area
            if memory_area == "holding_register":
                response = self._client.read_holding_registers(
                    batch.start,
                    count=batch.count,
                    device_id=unit_id,
                )
            elif memory_area == "input_register":
                response = self._client.read_input_registers(
                    batch.start,
                    count=batch.count,
                    device_id=unit_id,
                )
            else:
                raise RuntimeError(f"Unsupported Modbus register memory area: {memory_area}")
            if response.isError():
                raise RuntimeError(f"Modbus read error at {batch.start}")
            return response

        return self._retry_operation(
            operation="read",
            max_attempts=self._read_max_attempts,
            action=attempt,
            before_retry=self._reconnect_after_read_failure,
        )

    def _read_coil_batch_with_retry(self, batch: CoilBatch, unit_id: int) -> CoilReadResponseLike:
        """Read a coil batch with reconnect-aware retry semantics."""

        def attempt() -> CoilReadResponseLike:
            if self._client is None:
                raise RuntimeError("Modbus client not connected")
            memory_area = batch.specs[0].memory_area
            if memory_area == "coil":
                response = self._client.read_coils(
                    batch.start,
                    count=batch.count,
                    device_id=unit_id,
                )
            elif memory_area == "discrete_input":
                response = self._client.read_discrete_inputs(
                    batch.start,
                    count=batch.count,
                    device_id=unit_id,
                )
            else:
                raise RuntimeError(f"Unsupported Modbus binary memory area: {memory_area}")
            if response.isError():
                raise RuntimeError(f"Modbus binary read error at {batch.start}")
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

    def _retry_operation(
        self,
        operation: str,
        max_attempts: int,
        action: Callable[[], T],
        before_retry: Callable[[], None] | None = None,
    ) -> T:
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
            if spec.memory_area == current_specs[-1].memory_area and spec.address <= current_end:
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
    def _build_coil_batches(cls, specs: Sequence[CoilSpec]) -> list[CoilBatch]:
        """Group contiguous coils into shared reads."""
        if not specs:
            return []

        batches: list[CoilBatch] = []
        current_start = specs[0].address
        current_end = current_start + 1
        current_specs = [specs[0]]

        for spec in specs[1:]:
            spec_end = spec.address + 1
            if spec.memory_area == current_specs[-1].memory_area and spec.address <= current_end:
                current_end = max(current_end, spec_end)
                current_specs.append(spec)
                continue

            batches.append(
                CoilBatch(
                    start=current_start,
                    count=current_end - current_start,
                    specs=tuple(current_specs),
                )
            )
            current_start = spec.address
            current_end = spec_end
            current_specs = [spec]

        batches.append(
            CoilBatch(
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
            decoded: float | int = cls._decode_float32(list(registers))
        else:
            if not registers:
                raise RuntimeError(f"Missing register data at {spec.address}")
            decoded = int(registers[0])
        return cls._apply_scale_and_offset(decoded, spec)

    @staticmethod
    def _normalize_register_address(address: int, memory_area: str) -> int:
        """Normalize Modbus register addresses to zero-based offsets."""
        if memory_area == "holding_register" and address >= 40001:
            return address - 40001
        if memory_area == "input_register" and address >= 30001:
            return address - 30001
        return address

    @staticmethod
    def _normalize_binary_address(address: int, memory_area: str) -> int:
        """Normalize Modbus binary addresses to zero-based offsets."""
        if memory_area == "discrete_input" and address >= 10001:
            return address - 10001
        return max(address - 1, 0) if address > 0 else address

    @staticmethod
    def _decode_float32(registers: list[int]) -> float:
        """Decode two 16-bit registers into IEEE754 float32."""
        packed = bytes([registers[0] >> 8, registers[0] & 0xFF, registers[1] >> 8, registers[1] & 0xFF])
        return unpack(">f", packed)[0]

    @staticmethod
    def _apply_scale_and_offset(value: float | int, spec: RegisterSpec) -> float | int:
        adjusted = (float(value) * spec.scale) + spec.offset
        if spec.data_type in {"uint16", "int16"} and spec.scale == 1.0 and spec.offset == 0.0:
            return int(value)
        return adjusted

    @staticmethod
    def _sleep(seconds: float) -> None:
        """Pause between retries."""
        time.sleep(seconds)

    @staticmethod
    def _create_client(host: str, port: int) -> ModbusClientLike:
        """Construct a Modbus TCP client."""
        try:
            from pymodbus.client import ModbusTcpClient  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("pymodbus is required for ModbusTcpAdapter") from exc

        return ModbusTcpClient(host=host, port=port)

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
