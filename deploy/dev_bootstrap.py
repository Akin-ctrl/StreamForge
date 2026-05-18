"""Bootstrap the dev stack through the control-plane API."""

from __future__ import annotations

import json
import os
import sys
import time
from urllib import error, parse, request


CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://control_plane:8000").rstrip("/")
DEV_ADMIN_USERNAME = os.getenv("DEV_ADMIN_USERNAME", "streamforge_admin")
DEV_ADMIN_PASSWORD = os.getenv("DEV_ADMIN_PASSWORD", "LocalAdminBootstrap42")
GATEWAY_ID = os.getenv("CONTROL_PLANE_GATEWAY_ID", "gateway-demo-01")
DEPLOYMENT_ID = os.getenv("DEV_DEPLOYMENT_ID", "deployment-demo-01")
DEPLOYMENT_NAME = os.getenv("DEV_DEPLOYMENT_NAME", "Demo Deployment")
CONFIG_PATH = os.getenv("DEV_GATEWAY_CONFIG_PATH", "/app/deploy/gateway_config.sample.json")

_SECRET_FIELDS: dict[tuple[str, str], tuple[str, ...]] = {
    ("adapter", "mqtt"): ("password",),
    ("adapter", "opcua"): ("password",),
    ("sink", "timescaledb"): ("db_dsn",),
    ("sink", "alert_router"): ("url", "webhook_url"),
}


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _http_json(path: str, method: str = "GET", payload: dict | None = None, token: str | None = None):
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = request.Request(f"{CONTROL_PLANE_URL}{path}", data=data, method=method, headers=headers)
    with request.urlopen(req, timeout=10) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else None


def _secret_fields_for(kind: str, object_type: str) -> tuple[str, ...]:
    return _SECRET_FIELDS.get((kind, object_type), ())


def _split_config_payload(kind: str, object_type: str, config: dict) -> tuple[dict, dict[str, str]]:
    sanitized = dict(config)
    secrets: dict[str, str] = {}
    for field_name in _secret_fields_for(kind, object_type):
        secret_value = sanitized.pop(field_name, None)
        if isinstance(secret_value, str) and secret_value.strip():
            secrets[field_name] = secret_value.strip()
    return sanitized, secrets


def _wait_for_health(timeout_s: int = 120) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            payload = _http_json("/api/v1/health")
            if isinstance(payload, dict) and payload.get("status") == "healthy":
                return
        except Exception:
            time.sleep(2)
            continue
        time.sleep(2)
    raise RuntimeError("control plane did not become healthy before timeout")


def _ensure_admin_token() -> str:
    status = _http_json("/api/v1/auth/bootstrap/status")
    if status.get("bootstrap_required"):
        payload = _http_json(
            "/api/v1/auth/bootstrap/first-user",
            method="POST",
            payload={"username": DEV_ADMIN_USERNAME, "password": DEV_ADMIN_PASSWORD},
        )
        return str(payload["access_token"])

    form = parse.urlencode({"username": DEV_ADMIN_USERNAME, "password": DEV_ADMIN_PASSWORD}).encode("utf-8")
    req = request.Request(
        f"{CONTROL_PLANE_URL}/api/v1/auth/token",
        data=form,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    with request.urlopen(req, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return str(payload["access_token"])


def _ensure_gateway(token: str) -> None:
    gateways = _http_json("/api/v1/gateways", token=token)
    existing = next((item for item in gateways if item.get("gateway_id") == GATEWAY_ID), None)
    if existing is None:
        _http_json(
            "/api/v1/gateways",
            method="POST",
            token=token,
            payload={
                "gateway_id": GATEWAY_ID,
                "hostname": f"{GATEWAY_ID}.local",
                "hardware_info": {"environment": "dev-compose"},
                "approved": True,
            },
        )
        return
    if not existing.get("approved"):
        _http_json(f"/api/v1/gateways/{GATEWAY_ID}/approve", method="POST", token=token)


def _adapter_payload(adapter_cfg: dict) -> dict:
    adapter_id = str(adapter_cfg["adapter_id"])
    sanitized_config, secrets = _split_config_payload("adapter", str(adapter_cfg["adapter_type"]), adapter_cfg["config"])
    return {
        "adapter_id": adapter_id,
        "name": str(adapter_cfg.get("name") or adapter_id),
        "adapter_type": adapter_cfg["adapter_type"],
        "status": adapter_cfg.get("status", "active"),
        "config": sanitized_config,
        **({"secrets": secrets} if secrets else {}),
        "description": adapter_cfg.get("description"),
    }


def _sink_payload(sink_cfg: dict) -> dict:
    sink_id = str(sink_cfg["sink_id"])
    sanitized_config, secrets = _split_config_payload("sink", str(sink_cfg["sink_type"]), sink_cfg["config"])
    return {
        "sink_id": sink_id,
        "name": str(sink_cfg.get("name") or sink_id),
        "sink_type": sink_cfg["sink_type"],
        "status": sink_cfg.get("status", "active"),
        "config": sanitized_config,
        **({"secrets": secrets} if secrets else {}),
        "description": sink_cfg.get("description"),
    }


def _ensure_adapters(token: str, raw_config: dict) -> list[str]:
    adapters = _http_json("/api/v1/adapters", token=token)
    existing = {item["adapter_id"]: item for item in adapters}
    adapter_ids: list[str] = []

    for adapter_cfg in raw_config.get("adapters", []):
        payload = _adapter_payload(adapter_cfg)
        adapter_id = payload["adapter_id"]
        adapter_ids.append(adapter_id)
        current = existing.get(adapter_id)
        if current is None:
            _http_json("/api/v1/adapters", method="POST", token=token, payload=payload)
            continue
        if any(current.get(field) != payload[field] for field in ("name", "adapter_type", "status", "config", "description")) or bool(payload.get("secrets")):
            _http_json(f"/api/v1/adapters/{adapter_id}", method="PUT", token=token, payload=payload)

    return adapter_ids


def _ensure_sinks(token: str, raw_config: dict) -> list[str]:
    sinks = _http_json("/api/v1/sinks", token=token)
    existing = {item["sink_id"]: item for item in sinks}
    sink_ids: list[str] = []

    for sink_cfg in raw_config.get("sinks", []):
        payload = _sink_payload(sink_cfg)
        sink_id = payload["sink_id"]
        sink_ids.append(sink_id)
        current = existing.get(sink_id)
        if current is None:
            _http_json("/api/v1/sinks", method="POST", token=token, payload=payload)
            continue
        if any(current.get(field) != payload[field] for field in ("name", "sink_type", "status", "config", "description")) or bool(payload.get("secrets")):
            _http_json(f"/api/v1/sinks/{sink_id}", method="PUT", token=token, payload=payload)

    return sink_ids


def _ensure_deployment(token: str, raw_config: dict, adapter_ids: list[str], sink_ids: list[str]) -> None:
    deployments = _http_json("/api/v1/deployments", token=token)
    existing = next((item for item in deployments if item.get("deployment_id") == DEPLOYMENT_ID), None)
    payload = {
        "deployment_id": DEPLOYMENT_ID,
        "name": DEPLOYMENT_NAME,
        "gateway_id": GATEWAY_ID,
        "status": "active",
        "adapter_ids": adapter_ids,
        "sink_ids": sink_ids,
        "validation_config": raw_config.get("validation", {}),
        "events_config": raw_config.get("events", {}),
        "aggregates_config": raw_config.get("aggregates", {}),
    }

    if existing is None:
        _http_json("/api/v1/deployments", method="POST", token=token, payload=payload)
        return

    if any(
        existing.get(field) != payload[field]
        for field in (
            "name",
            "gateway_id",
            "status",
            "adapter_ids",
            "sink_ids",
            "validation_config",
            "events_config",
            "aggregates_config",
        )
    ):
        _http_json(f"/api/v1/deployments/{DEPLOYMENT_ID}", method="PUT", token=token, payload=payload)


def main() -> int:
    try:
        _wait_for_health()
        token = _ensure_admin_token()
        raw_config = _read_json(CONFIG_PATH)
        _ensure_gateway(token)
        adapter_ids = _ensure_adapters(token, raw_config)
        sink_ids = _ensure_sinks(token, raw_config)
        _ensure_deployment(token, raw_config, adapter_ids, sink_ids)
    except error.HTTPError as exc:
        sys.stderr.write(f"bootstrap failed with HTTP {exc.code}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"bootstrap failed: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
