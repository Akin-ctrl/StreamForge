"""Factory for creating adapter instances from config."""

from adapters.adapter_mqtt.mqtt_adapter import MqttAdapter
from adapters.adapter_opcua.opcua_adapter import OpcUaAdapter
from adapters.adapter_modbus_rtu.modbus_rtu_adapter import ModbusRtuAdapter
from adapters.adapter_modbus_tcp.modbus_tcp_adapter import ModbusTcpAdapter
from gateway_runtime.config import AdapterConfig
from gateway_runtime.errors import AdapterStartError


class AdapterFactory:
    """
    Factory for creating adapters from config.
    """

    def create(self, config: AdapterConfig):
        """Create adapter instance from config."""
        if config.adapter_type == "modbus_tcp":
            return ModbusTcpAdapter(config.config)
        if config.adapter_type == "modbus_rtu":
            return ModbusRtuAdapter(config.config)
        if config.adapter_type == "mqtt":
            return MqttAdapter(config.config)
        if config.adapter_type == "opcua":
            return OpcUaAdapter(config.config)

        raise AdapterStartError(f"Unsupported adapter type: {config.adapter_type}")
