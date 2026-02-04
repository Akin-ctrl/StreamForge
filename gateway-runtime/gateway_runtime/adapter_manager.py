"""Adapter manager for starting and monitoring adapters."""

from typing import Dict, List

from gateway_runtime.adapter_factory import AdapterFactory
from gateway_runtime.config import AdapterConfig


class AdapterManager:
    """
    Starts and monitors adapter instances.

    Uses AdapterFactory to create adapters from config.
    """

    def __init__(self, factory: AdapterFactory) -> None:
        """Initialize manager with adapter factory."""

    def start_all(self, configs: List[AdapterConfig]) -> None:
        """Start all adapters defined in config."""

    def stop_all(self) -> None:
        """Stop all running adapters."""

    def restart(self, adapter_id: str) -> None:
        """Restart a specific adapter by ID."""

    def health(self) -> Dict[str, object]:
        """Return health status for all adapters."""
