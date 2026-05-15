"""Gateway configuration models and repository."""

from dataclasses import dataclass
from pathlib import Path
from typing import List
import json
import os
import time
from urllib import request, error

from gateway_runtime.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
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
    events: dict
    aggregates: dict
    version: str | None = None


class ConfigRepository:
    """
    Repository for loading configuration.

    Loads static config from local file.
    Future versions can swap the source to the Control Plane API.
    """

    def __init__(self, path: str, schema_path: str | None = None) -> None:
        """Initialize with config file path and optional schema path."""
        self._path = Path(path)
        self._last_load_source = "file"
        if schema_path is None:
            repo_root = Path(__file__).resolve().parents[1]
            self._schema_path = repo_root / "schemas" / "gateway_config.schema.json"
        else:
            self._schema_path = Path(schema_path)

    @property
    def last_load_source(self) -> str:
        """Return the source used for the most recent successful load."""
        return self._last_load_source

    def load(self) -> GatewayConfig:
        """Load and validate gateway configuration."""
        if not self._path.exists():
            raise ConfigError(f"Config file not found: {self._path}")

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in config file: {exc}") from exc

        return self._config_from_raw(raw, source="file")

    def refresh(self) -> GatewayConfig:
        """Refresh configuration from its authoritative source."""
        return self.load()

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
        if "events" in raw and not isinstance(raw["events"], dict):
            raise ConfigError("'events' must be an object")
        if "aggregates" in raw and not isinstance(raw["aggregates"], dict):
            raise ConfigError("'aggregates' must be an object")

    def _config_from_raw(self, raw: dict, source: str) -> GatewayConfig:
        """Validate and hydrate a strongly typed gateway config."""
        self._validate(raw)
        self._last_load_source = source

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
            events=raw.get("events", {}),
            aggregates=raw.get("aggregates", {}),
            version=str(raw["version"]) if "version" in raw and raw["version"] is not None else None,
        )


class ControlPlaneConfigRepository(ConfigRepository):
    """Repository that loads gateway configuration from Control Plane API."""

    def __init__(
        self,
        base_url: str,
        gateway_id: str,
        token: str | None = None,
        cache_path: str | None = None,
        schema_path: str | None = None,
    ) -> None:
        super().__init__(path=cache_path or "/data/config/gateway.json", schema_path=schema_path)
        self._base_url = base_url.rstrip("/")
        self._gateway_id = gateway_id
        self._token = token
        self._token_refreshed_at = time.time()
        self._breaker = CircuitBreaker(
            name="control_plane",
            failure_threshold=int(os.getenv("CONTROL_PLANE_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")),
            open_duration_seconds=float(os.getenv("CONTROL_PLANE_CIRCUIT_BREAKER_OPEN_SECONDS", "30")),
        )

    @property
    def gateway_id(self) -> str:
        return self._gateway_id

    def load(self) -> GatewayConfig:
        """Load config for startup using cache-first gateway autonomy semantics."""
        cached_error: ConfigError | None = None

        if self._path.exists():
            try:
                return self._load_cached_config()
            except ConfigError as exc:
                cached_error = exc

        try:
            return self.refresh()
        except ConfigError as exc:
            if cached_error is not None:
                raise ConfigError(
                    f"Cached config is invalid and control-plane refresh failed: {exc}"
                ) from exc
            raise

    def refresh(self) -> GatewayConfig:
        """Fetch the latest config from the control plane and update the local cache."""
        raw = self.get_json(f"/api/v1/gateways/{self._gateway_id}/config")
        self._assert_gateway_identity(raw)
        config = self._config_from_raw(raw, source="control_plane")
        self._write_cache(raw)
        return config

    def health(self) -> dict[str, object]:
        """Return control-plane connectivity and cache health details."""
        breaker = self._breaker.snapshot()
        status = "healthy"
        if breaker.state == "open":
            status = "failed"
        elif breaker.state == "half_open" or breaker.last_error is not None:
            status = "degraded"

        return {
            "status": status,
            "gateway_id": self._gateway_id,
            "cache_path": str(self._path),
            "cache_present": self._path.exists(),
            "last_load_source": self.last_load_source,
            "circuit_breaker": {
                "name": breaker.name,
                "state": breaker.state,
                "consecutive_failures": breaker.consecutive_failures,
                "failure_threshold": breaker.failure_threshold,
                "open_remaining_seconds": breaker.open_remaining_seconds,
                "last_error": breaker.last_error,
            },
        }

    def get_json(self, path: str, authenticated: bool = True) -> dict:
        """GET a JSON resource from the control plane."""
        data = self._request_json(path=path, method="GET", payload=None, authenticated=authenticated)
        if not isinstance(data, dict):
            raise ConfigError("Control Plane returned an unexpected JSON payload")
        return data

    def get_json_list(self, path: str, authenticated: bool = True) -> list[dict]:
        """GET a JSON list resource from the control plane."""
        data = self._request_json(path=path, method="GET", payload=None, authenticated=authenticated)
        if not isinstance(data, list):
            raise ConfigError("Control Plane returned an unexpected JSON payload")
        return data

    def post_json(self, path: str, payload: dict, authenticated: bool = True) -> dict:
        """POST JSON to the control plane and return the JSON response."""
        data = self._request_json(path=path, method="POST", payload=payload, authenticated=authenticated)
        if not isinstance(data, dict):
            raise ConfigError("Control Plane returned an unexpected JSON payload")
        return data

    def _request_json(
        self,
        path: str,
        method: str,
        payload: dict | None,
        authenticated: bool,
        retried_after_refresh: bool = False,
    ) -> dict | list:
        request_payload = None
        headers = {"Accept": "application/json"}

        try:
            self._breaker.ensure_request_allowed()
        except CircuitBreakerOpenError as exc:
            raise ConfigError(str(exc)) from exc

        if payload is not None:
            request_payload = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        if authenticated:
            self._ensure_token()
            headers["Authorization"] = f"Bearer {self._token}"

        req = request.Request(
            f"{self._base_url}{path}",
            data=request_payload,
            method=method,
            headers=headers,
        )
        try:
            with request.urlopen(req, timeout=10) as response:
                response_payload = response.read().decode("utf-8")
        except error.HTTPError as exc:
            if authenticated and exc.code == 401 and not retried_after_refresh:
                self._refresh_token()
                return self._request_json(
                    path=path,
                    method=method,
                    payload=payload,
                    authenticated=authenticated,
                    retried_after_refresh=True,
                )
            self._breaker.record_failure(exc)
            raise ConfigError(f"Control Plane request failed: HTTP {exc.code}") from exc
        except error.URLError as exc:
            self._breaker.record_failure(exc)
            raise ConfigError(f"Control Plane request failed: {exc.reason}") from exc

        try:
            data = json.loads(response_payload)
        except json.JSONDecodeError as exc:
            self._breaker.record_failure(exc)
            raise ConfigError(f"Control Plane returned invalid JSON: {exc}") from exc
        self._breaker.record_success()
        return data

    def _ensure_token(self) -> None:
        if not self._token:
            self._request_gateway_token()

        if time.time() - self._token_refreshed_at > 86400:
            self._refresh_token()

    def _refresh_token(self) -> None:
        """Refresh the gateway token from the control plane."""
        self._request_gateway_token()

    def _request_gateway_token(self) -> None:
        """Request a gateway token from control plane using gateway_id."""
        try:
            self._breaker.ensure_request_allowed()
        except CircuitBreakerOpenError as exc:
            raise ConfigError(str(exc)) from exc

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
            self._breaker.record_failure(exc)
            raise ConfigError(f"Gateway token request failed: HTTP {exc.code}") from exc
        except error.URLError as exc:
            self._breaker.record_failure(exc)
            raise ConfigError(f"Gateway token request failed: {exc.reason}") from exc
        
        try:
            data = json.loads(payload)
            self._token = data.get("token")
            if not self._token:
                empty_token_error = ConfigError("Gateway token request returned empty token")
                self._breaker.record_failure(empty_token_error)
                raise empty_token_error
            self._token_refreshed_at = time.time()
        except json.JSONDecodeError as exc:
            self._breaker.record_failure(exc)
            raise ConfigError(f"Gateway token request returned invalid JSON: {exc}") from exc
        self._breaker.record_success()

    def _load_cached_config(self) -> GatewayConfig:
        """Load and validate cached config for offline startup."""
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in cached config: {exc}") from exc

        self._assert_gateway_identity(raw)
        return self._config_from_raw(raw, source="cache")

    def _assert_gateway_identity(self, raw: dict) -> None:
        """Reject payloads that do not belong to the configured gateway."""
        gateway_id = raw.get("gateway_id")
        if gateway_id != self._gateway_id:
            raise ConfigError(
                f"Gateway config identity mismatch: expected '{self._gateway_id}', got '{gateway_id}'"
            )

    def _write_cache(self, raw: dict) -> None:
        """Persist control-plane config atomically for offline reuse."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        tmp_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp_path.replace(self._path)
