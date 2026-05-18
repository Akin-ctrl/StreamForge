#!/usr/bin/env bash
# seed_dev.sh — Seeds a demo gateway deployment into the control plane for local development.
# Safe to run multiple times: adapters, sinks, and deployment records are created or updated in place.
#
# Usage:
#   ./seed_dev.sh [CONTROL_PLANE_URL]
#
# Defaults to http://localhost:8001 if no argument is given.

set -euo pipefail

BASE_URL="${1:-http://localhost:8001}"
GATEWAY_ID="gateway-demo-01"
DEPLOYMENT_ID="deployment-demo-01"
DEPLOYMENT_NAME="Demo Deployment"
ADMIN_USER="streamforge_admin"
ADMIN_PASS="LocalAdminBootstrap42"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[seed]${NC} $*"; }
warn()    { echo -e "${YELLOW}[seed]${NC} $*"; }
err()     { echo -e "${RED}[seed]${NC} $*" >&2; }

CONFIG_JSON=$(cat <<'JSON'
{
  "adapters": [
    {
      "adapter_id": "modbus-demo-01",
      "name": "Demo Modbus Adapter",
      "adapter_type": "modbus_tcp",
      "status": "active",
      "config": {
        "host": "modbus-simulator",
        "port": 5020,
        "unit_id": 1,
        "poll_interval_ms": 1000,
        "registers": [
          {"address": 40001, "param": "temperature", "type": "float32", "unit": "celsius"}
        ],
        "coils": [
          {"address": 1, "param": "motor_running", "event_type": "motor_state_change"}
        ],
        "output": {
          "kafka_bootstrap": "kafka:9092",
          "topic": "telemetry.raw",
          "events_topic": "events.raw",
          "asset_id": "demo_sensor_01"
        }
      }
    }
  ],
  "validation": {
    "enabled": true,
    "raw_topic": "telemetry.raw",
    "clean_topic": "telemetry.clean",
    "dlq_topic": "dlq.telemetry",
    "ranges": {
      "temperature": {"min": -50, "max": 500}
    },
    "rate_of_change": {
      "temperature": 20
    },
    "gap_detection": {
      "temperature": 5
    },
    "alarm_topic": "alarms.raw",
    "alarm_rules": [
      {
        "parameter": "temperature",
        "condition": "value > 100",
        "severity": "HIGH",
        "type": "temperature_high",
        "message": "Temperature exceeded configured threshold"
      }
    ]
  },
  "events": {
    "enabled": true,
    "raw_topic": "events.raw",
    "clean_topic": "events.clean",
    "dlq_topic": "dlq.events"
  },
  "aggregates": {
    "enabled": true,
    "source_topic": "telemetry.clean",
    "resolutions": {
      "1s": {
        "enabled": true,
        "topic": "telemetry.1s",
        "window_seconds": 1
      },
      "1min": {
        "enabled": true,
        "topic": "telemetry.1min",
        "window_seconds": 60
      }
    }
  },
  "sinks": [
    {
      "sink_id": "timescaledb-primary",
      "name": "Primary TimescaleDB Sink",
      "sink_type": "timescaledb",
      "status": "active",
      "config": {
        "kafka_bootstrap": "kafka:9092",
        "topic": "telemetry.clean",
        "group_id": "sf-sink-timescaledb",
        "db_dsn": "postgresql://streamforge:streamforge@timescaledb:5432/streamforge",
        "table": "telemetry_clean"
      }
    }
  ]
}
JSON
)

info "Checking bootstrap state at $BASE_URL ..."
BOOTSTRAP_RESP=$(curl -sf "$BASE_URL/api/v1/auth/bootstrap/status") || {
  err "Could not reach control plane at $BASE_URL. Is it running?"
  exit 1
}
BOOTSTRAP_REQUIRED=$(echo "$BOOTSTRAP_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if d.get('bootstrap_required') else 'no')")

if [[ "$BOOTSTRAP_REQUIRED" == "yes" ]]; then
  info "Bootstrapping the first admin account ..."
  BOOTSTRAP_PAYLOAD=$(python3 -c "
import json
print(json.dumps({'username': '$ADMIN_USER', 'password': '$ADMIN_PASS'}))
")
  TOKEN_RESP=$(curl -sf -X POST "$BASE_URL/api/v1/auth/bootstrap/first-user" \
    -H "Content-Type: application/json" \
    -d "$BOOTSTRAP_PAYLOAD") || {
    err "First-user bootstrap failed."
    exit 1
  }
else
  info "Requesting admin token from $BASE_URL ..."
  TOKEN_RESP=$(curl -sf -X POST "$BASE_URL/api/v1/auth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$ADMIN_USER&password=$ADMIN_PASS") || {
    err "Could not authenticate with the configured admin credentials."
    exit 1
  }
fi

TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))")
if [[ -z "$TOKEN" ]]; then
  err "Auth failed — check bootstrap or admin credentials."
  exit 1
fi
info "Admin token acquired."

_get()  { curl -sf -H "Authorization: Bearer $TOKEN" "$BASE_URL$1"; }
_post() { curl -sf -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$2" "$BASE_URL$1"; }
_put()  { curl -sf -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$2" "$BASE_URL$1"; }

info "Checking gateway '$GATEWAY_ID' ..."
GW_LIST=$(_get "/api/v1/gateways")
GW_EXISTS=$(echo "$GW_LIST" | python3 -c "
import sys, json
gws = json.load(sys.stdin)
print('yes' if any(g['gateway_id'] == '$GATEWAY_ID' for g in gws) else 'no')
")

if [[ "$GW_EXISTS" != "yes" ]]; then
  warn "Gateway '$GATEWAY_ID' is missing. Creating it via admin API ..."
  GATEWAY_PAYLOAD=$(python3 -c "
import json
payload = {
    'gateway_id': '$GATEWAY_ID',
    'hostname': 'gateway-demo-01.local',
    'approved': True,
}
print(json.dumps(payload))
")
  _post "/api/v1/gateways" "$GATEWAY_PAYLOAD" >/dev/null
fi
info "Gateway '$GATEWAY_ID' found."

info "Upserting adapters, sinks, and deployment ..."
python3 - "$BASE_URL" "$TOKEN" "$GATEWAY_ID" "$DEPLOYMENT_ID" "$DEPLOYMENT_NAME" "$CONFIG_JSON" <<'PY'
import json
import sys
from urllib import request

base_url, token, gateway_id, deployment_id, deployment_name, raw_config = sys.argv[1:]
config = json.loads(raw_config)

SECRET_FIELDS = {
    ("adapter", "mqtt"): ("password",),
    ("adapter", "opcua"): ("password",),
    ("sink", "timescaledb"): ("db_dsn",),
    ("sink", "alert_router"): ("url", "webhook_url"),
}

def http_json(path: str, method: str = "GET", payload: dict | None = None):
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    with request.urlopen(req, timeout=10) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else None


def secret_fields_for(kind: str, object_type: str) -> tuple[str, ...]:
    return SECRET_FIELDS.get((kind, object_type), ())


def split_config_payload(kind: str, object_type: str, payload_config: dict) -> tuple[dict, dict[str, str]]:
    sanitized = dict(payload_config)
    secrets: dict[str, str] = {}
    for field_name in secret_fields_for(kind, object_type):
        secret_value = sanitized.pop(field_name, None)
        if isinstance(secret_value, str) and secret_value.strip():
            secrets[field_name] = secret_value.strip()
    return sanitized, secrets


adapters = {item["adapter_id"]: item for item in http_json("/api/v1/adapters")}
adapter_ids = []
for adapter in config.get("adapters", []):
    sanitized_config, secrets = split_config_payload("adapter", adapter["adapter_type"], adapter["config"])
    payload = {
        "adapter_id": adapter["adapter_id"],
        "name": adapter.get("name") or adapter["adapter_id"],
        "adapter_type": adapter["adapter_type"],
        "status": adapter.get("status", "active"),
        "config": sanitized_config,
        "description": adapter.get("description"),
    }
    if secrets:
        payload["secrets"] = secrets
    adapter_ids.append(payload["adapter_id"])
    existing = adapters.get(payload["adapter_id"])
    if existing is None:
        http_json("/api/v1/adapters", method="POST", payload=payload)
    elif any(existing.get(field) != payload[field] for field in ("name", "adapter_type", "status", "config", "description")) or bool(payload.get("secrets")):
        http_json(f"/api/v1/adapters/{payload['adapter_id']}", method="PUT", payload=payload)

sinks = {item["sink_id"]: item for item in http_json("/api/v1/sinks")}
sink_ids = []
for sink in config.get("sinks", []):
    sanitized_config, secrets = split_config_payload("sink", sink["sink_type"], sink["config"])
    payload = {
        "sink_id": sink["sink_id"],
        "name": sink.get("name") or sink["sink_id"],
        "sink_type": sink["sink_type"],
        "status": sink.get("status", "active"),
        "config": sanitized_config,
        "description": sink.get("description"),
    }
    if secrets:
        payload["secrets"] = secrets
    sink_ids.append(payload["sink_id"])
    existing = sinks.get(payload["sink_id"])
    if existing is None:
        http_json("/api/v1/sinks", method="POST", payload=payload)
    elif any(existing.get(field) != payload[field] for field in ("name", "sink_type", "status", "config", "description")) or bool(payload.get("secrets")):
        http_json(f"/api/v1/sinks/{payload['sink_id']}", method="PUT", payload=payload)

payload = {
    "deployment_id": deployment_id,
    "name": deployment_name,
    "gateway_id": gateway_id,
    "status": "active",
    "adapter_ids": adapter_ids,
    "sink_ids": sink_ids,
    "validation_config": config.get("validation", {}),
    "events_config": config.get("events", {}),
    "aggregates_config": config.get("aggregates", {}),
}
deployments = {item["deployment_id"]: item for item in http_json("/api/v1/deployments")}
existing = deployments.get(deployment_id)
if existing is None:
    http_json("/api/v1/deployments", method="POST", payload=payload)
elif any(
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
    http_json(f"/api/v1/deployments/{deployment_id}", method="PUT", payload=payload)
PY

echo ""
info "Done. Demo topology is seeded:"
info "  Gateway    : $GATEWAY_ID"
info "  Deployment : $DEPLOYMENT_ID"
info "  Adapter    : modbus-demo-01"
info "  Sink       : timescaledb-primary"
echo ""
warn "If gateway_runtime is already running, it will pick up the new config within GATEWAY_POLL_INTERVAL seconds (default 30s)."
warn "Or restart it now: docker compose -f deploy/docker-compose.dev.yml restart gateway_runtime"
