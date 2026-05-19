"""Modbus RTU adapter implementation."""

from __future__ import annotations

from adapters.adapter_modbus_tcp.modbus_tcp_adapter import ModbusClientLike, ModbusTcpAdapter


class ModbusRtuAdapter(ModbusTcpAdapter):
    """Modbus RTU adapter that reuses the shared Modbus polling pipeline."""

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._health.update(
            {
                "transport": "rtu",
                "serial_port": str(config.get("port", "")),
                "baudrate": int(config.get("baudrate", 9600)),
                "bytesize": int(config.get("bytesize", 8)),
                "parity": str(config.get("parity", "N")),
                "stopbits": int(config.get("stopbits", 1)),
                "timeout_seconds": float(config.get("timeout", 1.0)),
            }
        )

    def connect(self) -> None:
        """Connect to a Modbus RTU serial device."""
        serial_port = str(self.config.get("port") or self.config.get("device") or "").strip()
        if not serial_port:
            raise RuntimeError("Modbus RTU adapter requires 'port' or 'device'")

        baudrate = int(self.config.get("baudrate", 9600))
        bytesize = int(self.config.get("bytesize", 8))
        parity = str(self.config.get("parity", "N"))
        stopbits = int(self.config.get("stopbits", 1))
        timeout = float(self.config.get("timeout", 1.0))

        def attempt() -> None:
            self.disconnect()
            client = self._create_serial_client(
                port=serial_port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=timeout,
            )
            if not client.connect():
                raise RuntimeError(f"Unable to connect to Modbus RTU device {serial_port}")
            self._client = client
            self._health["connected"] = True

        self._retry_operation(
            operation="connect",
            max_attempts=self._connect_max_attempts,
            action=attempt,
        )

    @staticmethod
    def _create_serial_client(
        *,
        port: str,
        baudrate: int,
        bytesize: int,
        parity: str,
        stopbits: int,
        timeout: float,
    ) -> ModbusClientLike:
        """Construct a Modbus RTU serial client."""
        try:
            from pymodbus.client import ModbusSerialClient  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("pymodbus is required for ModbusRtuAdapter") from exc

        return ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=timeout,
        )
