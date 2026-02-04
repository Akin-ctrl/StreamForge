"""Gateway configuration models and repository."""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AdapterConfig:
    """Configuration for a single adapter instance."""

    adapter_id: str
    adapter_type: str
    config: dict


@dataclass(frozen=True)
class GatewayConfig:
    """Top-level configuration for the gateway runtime."""

    gateway_id: str
    adapters: List[AdapterConfig]


class ConfigRepository:
    """
    Repository for loading configuration.

    Phase 1: loads static config from local file.
    Phase 2: swap to Control Plane API.
    """

    def __init__(self, path: str) -> None:
        """Initialize with config file path."""

    def load(self) -> GatewayConfig:
        """Load and validate gateway configuration."""
