"""Factory for creating adapter instances from config."""

from adapters.adapter_modbus_tcp.modbus_tcp_adapter import ModbusTcpAdapter
from gateway_runtime.config import AdapterConfig
from gateway_runtime.errors import AdapterStartError


class AdapterFactory:
    """
    Factory for creating adapters from config.

    Phase 1 supports only Modbus TCP.
    """

    def create(self, config: AdapterConfig):
        """Create adapter instance from config."""
        if config.adapter_type == "modbus_tcp":
            return ModbusTcpAdapter(config.config)

        raise AdapterStartError(f"Unsupported adapter type: {config.adapter_type}")
