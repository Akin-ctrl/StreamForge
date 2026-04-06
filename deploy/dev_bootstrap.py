"""Bootstrap the dev stack through the control-plane API."""

from __future__ import annotations

import json
import os
import sys
import time
from urllib import error, parse, request


CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://control_plane:8000").rstrip("/")
DEV_ADMIN_USERNAME = os.getenv("DEV_ADMIN_USERNAME", "streamforge_admin")
DEV_ADMIN_PASSWORD = os.getenv("DEV_ADMIN_PASSWORD", "StreamForge1234")
GATEWAY_ID = os.getenv("CONTROL_PLANE_GATEWAY_ID", "gateway-demo-01")
PIPELINE_NAME = os.getenv("DEV_PIPELINE_NAME", "demo-pipeline")
CONFIG_PATH = os.getenv("DEV_GATEWAY_CONFIG_PATH", "/app/deploy/gateway_config.sample.json")


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


def _ensure_pipeline_and_sinks(token: str, raw_config: dict) -> None:
    pipeline_config = {
        "adapters": raw_config.get("adapters", []),
        "validation": raw_config.get("validation", {}),
    }

    pipelines = _http_json("/api/v1/pipelines", token=token)
    pipeline = next(
        (item for item in pipelines if item.get("gateway_id") == GATEWAY_ID and item.get("name") == PIPELINE_NAME),
        None,
    )
    if pipeline is None:
        pipeline = _http_json(
            "/api/v1/pipelines",
            method="POST",
            token=token,
            payload={"name": PIPELINE_NAME, "gateway_id": GATEWAY_ID, "config": pipeline_config},
        )
    elif pipeline.get("config") != pipeline_config:
        pipeline = _http_json(
            f"/api/v1/pipelines/{pipeline['id']}",
            method="PUT",
            token=token,
            payload={"name": PIPELINE_NAME, "config": pipeline_config},
        )

    sinks = _http_json("/api/v1/sinks", token=token)
    pipeline_id = int(pipeline["id"])
    for sink_cfg in raw_config.get("sinks", []):
        existing = next(
            (
                item
                for item in sinks
                if int(item.get("pipeline_id")) == pipeline_id and item.get("sink_type") == sink_cfg.get("sink_type")
            ),
            None,
        )
        payload = {
            "pipeline_id": pipeline_id,
            "sink_type": sink_cfg["sink_type"],
            "config": sink_cfg["config"],
            "status": sink_cfg.get("status", "active"),
        }
        if existing is None:
            _http_json("/api/v1/sinks", method="POST", token=token, payload=payload)
        elif existing.get("config") != payload["config"] or existing.get("status") != payload["status"]:
            _http_json(f"/api/v1/sinks/{existing['id']}", method="PUT", token=token, payload=payload)


def main() -> int:
    try:
        _wait_for_health()
        token = _ensure_admin_token()
        raw_config = _read_json(CONFIG_PATH)
        _ensure_gateway(token)
        _ensure_pipeline_and_sinks(token, raw_config)
    except error.HTTPError as exc:
        sys.stderr.write(f"bootstrap failed with HTTP {exc.code}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"bootstrap failed: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
