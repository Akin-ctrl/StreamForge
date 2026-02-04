"""Modbus TCP adapter skeleton."""

from typing import Dict

from adapter_base.base_adapter import BaseAdapter


class ModbusTcpAdapter(BaseAdapter):
    """
    Modbus TCP adapter implementation.

    Overrides BaseAdapter hooks for Modbus protocol.
    """

    def connect(self) -> None:
        """Connect to Modbus TCP server."""

    def poll(self) -> Dict[str, object]:
        """Poll configured registers."""

    def transform(self, raw: Dict[str, object]) -> Dict[str, object]:
        """Map registers to telemetry message."""
