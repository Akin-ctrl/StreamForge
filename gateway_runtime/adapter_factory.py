"""Factory for creating adapter instances from config."""

from gateway_runtime.config import AdapterConfig


class AdapterFactory:
    """
    Factory for creating adapters from config.

    Phase 1 supports only Modbus TCP.
    """

    def create(self, config: AdapterConfig):
        """Create adapter instance from config."""
