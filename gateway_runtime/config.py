"""Gateway configuration models and repository."""

from dataclasses import dataclass
from pathlib import Path
from typing import List
import json
import time
from urllib import request, error

from gateway_runtime.errors import ConfigError


@dataclass(frozen=True)
class AdapterConfig:
    """Configuration for a single adapter instance."""

    adapter_id: str
    adapter_type: str
    config: dict


@dataclass(frozen=True)
class SinkConfig:
    """Configuration for a single sink instance."""

    sink_id: str
    sink_type: str
    config: dict
    status: str = "active"


@dataclass(frozen=True)
class GatewayConfig:
    """Top-level configuration for the gateway runtime."""

    gateway_id: str
    adapters: List[AdapterConfig]
    sinks: List[SinkConfig]
    validation: dict


class ConfigRepository:
    """
    Repository for loading configuration.

    Loads static config from local file.
    Future versions can swap the source to the Control Plane API.
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

        sinks = [
            SinkConfig(
                sink_id=item.get("sink_id") or f"sink-{index}",
                sink_type=item["sink_type"],
                config=item["config"],
                status=item.get("status", "active"),
            )
            for index, item in enumerate(raw.get("sinks", []), start=1)
        ]

        return GatewayConfig(
            gateway_id=raw["gateway_id"],
            adapters=adapters,
            sinks=sinks,
            validation=raw.get("validation", {}),
        )

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

        if "sinks" in raw:
            if not isinstance(raw["sinks"], list):
                raise ConfigError("'sinks' must be a list")
            for item in raw["sinks"]:
                if not all(key in item for key in ("sink_type", "config")):
                    raise ConfigError("Each sink must include 'sink_type' and 'config'")

        if "validation" in raw and not isinstance(raw["validation"], dict):
            raise ConfigError("'validation' must be an object")


class ControlPlaneConfigRepository(ConfigRepository):
    """Repository that loads gateway configuration from Control Plane API."""

    def __init__(self, base_url: str, gateway_id: str, token: str | None = None, schema_path: str | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._gateway_id = gateway_id
        self._token = token
        self._token_refreshed_at = time.time()
        if schema_path is None:
            repo_root = Path(__file__).resolve().parents[1]
            self._schema_path = repo_root / "schemas" / "gateway_config.schema.json"
        else:
            self._schema_path = Path(schema_path)

    def load(self) -> GatewayConfig:
        """Load and validate gateway configuration from control plane."""
        if not self._token:
            self._request_gateway_token()

        # Refresh token if it's been > 24 hours since last refresh
        if time.time() - self._token_refreshed_at > 86400:
            self._refresh_token()
        
        url = f"{self._base_url}/api/v1/gateways/{self._gateway_id}/config"
        req = request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=10) as response:
                payload = response.read().decode("utf-8")
        except error.HTTPError as exc:
            raise ConfigError(f"Control Plane config request failed: HTTP {exc.code}") from exc
        except error.URLError as exc:
            raise ConfigError(f"Control Plane config request failed: {exc.reason}") from exc

        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Control Plane returned invalid JSON: {exc}") from exc

        self._validate(raw)

        adapters = [
            AdapterConfig(
                adapter_id=item["adapter_id"],
                adapter_type=item["adapter_type"],
                config=item["config"],
            )
            for item in raw["adapters"]
        ]

        sinks = [
            SinkConfig(
                sink_id=item.get("sink_id") or f"sink-{index}",
                sink_type=item["sink_type"],
                config=item["config"],
                status=item.get("status", "active"),
            )
            for index, item in enumerate(raw.get("sinks", []), start=1)
        ]

        return GatewayConfig(
            gateway_id=raw["gateway_id"],
            adapters=adapters,
            sinks=sinks,
            validation=raw.get("validation", {}),
        )

    def _refresh_token(self) -> None:
        """Refresh the gateway token from the control plane."""
        self._request_gateway_token()

    def _request_gateway_token(self) -> None:
        """Request a gateway token from control plane using gateway_id."""
        url = f"{self._base_url}/api/v1/gateways/token"
        payload = json.dumps({"gateway_id": self._gateway_id}).encode("utf-8")
        req = request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=10) as response:
                payload = response.read().decode("utf-8")
        except error.HTTPError as exc:
            if exc.code == 403:
                raise ConfigError(
                    "Gateway token request denied: gateway is pending approval"
                ) from exc
            if exc.code == 404:
                raise ConfigError(
                    "Gateway token request failed: gateway not registered"
                ) from exc
            raise ConfigError(f"Gateway token request failed: HTTP {exc.code}") from exc
        except error.URLError as exc:
            raise ConfigError(f"Gateway token request failed: {exc.reason}") from exc
        
        try:
            data = json.loads(payload)
            self._token = data.get("token")
            if not self._token:
                raise ConfigError("Gateway token request returned empty token")
            self._token_refreshed_at = time.time()
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Gateway token request returned invalid JSON: {exc}") from exc
