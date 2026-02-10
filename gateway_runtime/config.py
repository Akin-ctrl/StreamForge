"""Gateway configuration models and repository."""

from dataclasses import dataclass
from pathlib import Path
from typing import List
import json

from gateway_runtime.errors import ConfigError


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

    def __init__(self, path: str, schema_path: str | None = None) -> None:
        """Initialize with config file path and optional schema path."""
        self._path = Path(path)
        if schema_path is None:
            repo_root = Path(__file__).resolve().parents[1]
            self._schema_path = repo_root / "schemas" / "gateway_config.schema.json"
        else:
            self._schema_path = Path(schema_path)

    def load(self) -> GatewayConfig:
        """Load and validate gateway configuration."""
        if not self._path.exists():
            raise ConfigError(f"Config file not found: {self._path}")

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in config file: {exc}") from exc

        self._validate(raw)

        adapters = [
            AdapterConfig(
                adapter_id=item["adapter_id"],
                adapter_type=item["adapter_type"],
                config=item["config"],
            )
            for item in raw["adapters"]
        ]

        return GatewayConfig(gateway_id=raw["gateway_id"], adapters=adapters)

    def _validate(self, raw: dict) -> None:
        """Validate config against JSON Schema if available; fallback to basic checks."""
        if self._schema_path.exists():
            try:
                import jsonschema  # type: ignore

                schema = json.loads(self._schema_path.read_text(encoding="utf-8"))
                jsonschema.validate(instance=raw, schema=schema)
                return
            except ModuleNotFoundError:
                pass
            except Exception as exc:
                raise ConfigError(f"Config schema validation failed: {exc}") from exc

        if "gateway_id" not in raw or "adapters" not in raw:
            raise ConfigError("Config must include 'gateway_id' and 'adapters'")

        if not isinstance(raw.get("adapters"), list):
            raise ConfigError("'adapters' must be a list")

        for item in raw["adapters"]:
            if not all(key in item for key in ("adapter_id", "adapter_type", "config")):
                raise ConfigError("Each adapter must include 'adapter_id', 'adapter_type', and 'config'")
