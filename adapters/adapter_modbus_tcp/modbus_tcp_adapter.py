"""Modbus TCP adapter implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from struct import unpack
from typing import Dict, Iterable

from adapters.adapter_base.base_adapter import BaseAdapter


@dataclass(frozen=True)
class RegisterSpec:
    """Single Modbus register specification."""

    address: int
    param: str
    data_type: str
    unit: str


class ModbusTcpAdapter(BaseAdapter):
    """
    Modbus TCP adapter implementation.

    Overrides BaseAdapter hooks for Modbus protocol.
    """

    def __init__(self, config: dict) -> None:
        """Initialize adapter with validated config."""
        super().__init__(config)
        self._config = config
        self._client = None
        self._producer = None

    def connect(self) -> None:
        """Connect to Modbus TCP server."""
        try:
            from pymodbus.client import ModbusTcpClient  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("pymodbus is required for ModbusTcpAdapter") from exc

        host = self._config["host"]
        port = int(self._config.get("port", 502))
        self._client = ModbusTcpClient(host=host, port=port)
        if not self._client.connect():
            raise RuntimeError(f"Unable to connect to Modbus server {host}:{port}")

    def poll(self) -> Dict[str, object]:
        """Poll configured registers."""
        if self._client is None:
            raise RuntimeError("Modbus client not connected")

        unit_id = int(self._config.get("unit_id", 1))
        registers = list(self._iter_registers())
        readings: Dict[str, object] = {}

        for spec in registers:
            if spec.data_type == "float32":
                response = self._client.read_holding_registers(
                    spec.address,
                    count=2,
                    device_id=unit_id,
                )
                if response.isError():
                    raise RuntimeError(f"Modbus read error at {spec.address}")
                value = self._decode_float32(response.registers)
            else:
                response = self._client.read_holding_registers(
                    spec.address,
                    count=1,
                    device_id=unit_id,
                )
                if response.isError():
                    raise RuntimeError(f"Modbus read error at {spec.address}")
                value = response.registers[0]

            readings[spec.param] = {"value": value, "unit": spec.unit}

        return readings

    def transform(self, raw: Dict[str, object]) -> Dict[str, object]:
        """Map registers to telemetry message."""
        now = datetime.now(timezone.utc).isoformat()
        output = self._config["output"]
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

    def publish(self, message: Dict[str, object]) -> None:
        """Publish normalized message to Kafka."""
        try:
            from kafka import KafkaProducer  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("kafka-python is required for ModbusTcpAdapter") from exc

        if self._producer is None:
            output = self._config["output"]
            bootstrap = output["kafka_bootstrap"]
            self._producer = KafkaProducer(
                bootstrap_servers=bootstrap,
                value_serializer=lambda v: json_dumps(v).encode("utf-8"),
            )

        topic = self._config["output"]["topic"]
        self._producer.send(topic, message)
        self._producer.flush()

    def _iter_registers(self) -> Iterable[RegisterSpec]:
        """Yield register specs from configuration."""
        for item in self._config.get("registers", []):
            address = self._normalize_address(int(item["address"]))
            yield RegisterSpec(
                address=address,
                param=item["param"],
                data_type=item.get("type", "uint16"),
                unit=item.get("unit", "")
            )

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


def json_dumps(value: object) -> str:
    """Serialize to JSON without external dependencies."""
    import json

    return json.dumps(value)
