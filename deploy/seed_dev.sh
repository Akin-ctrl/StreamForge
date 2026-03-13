#!/usr/bin/env bash
# seed_dev.sh — Seeds a demo pipeline + sink into the control plane for local development.
# Safe to run multiple times: skips creation if the pipeline already exists for the gateway.
#
# Usage:
#   ./seed_dev.sh [CONTROL_PLANE_URL]
#
# Defaults to http://localhost:8001 if no argument is given.

set -euo pipefail

BASE_URL="${1:-http://localhost:8001}"
GATEWAY_ID="gateway-demo-01"
ADMIN_USER="admin"
ADMIN_PASS="admin123"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[seed]${NC} $*"; }
warn()    { echo -e "${YELLOW}[seed]${NC} $*"; }
err()     { echo -e "${RED}[seed]${NC} $*" >&2; }

# ── 1. Get admin token ────────────────────────────────────────────────────────
info "Requesting admin token from $BASE_URL ..."
TOKEN_RESP=$(curl -sf -X POST "$BASE_URL/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$ADMIN_USER&password=$ADMIN_PASS") || {
  err "Could not reach control plane at $BASE_URL. Is it running?"
  exit 1
}

TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))")
if [[ -z "$TOKEN" ]]; then
  err "Auth failed — check admin credentials."
  exit 1
fi
info "Admin token acquired."

AUTH="-H \"Authorization: Bearer $TOKEN\""

_get()  { curl -sf -H "Authorization: Bearer $TOKEN" "$BASE_URL$1"; }
_post() { curl -sf -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$2" "$BASE_URL$1"; }

# ── 2. Verify gateway is registered ──────────────────────────────────────────
info "Checking gateway '$GATEWAY_ID' ..."
GW_LIST=$(_get "/api/v1/gateways")
GW_EXISTS=$(echo "$GW_LIST" | python3 -c "
import sys, json
gws = json.load(sys.stdin)
print('yes' if any(g['gateway_id'] == '$GATEWAY_ID' for g in gws) else 'no')
")

if [[ "$GW_EXISTS" != "yes" ]]; then
  err "Gateway '$GATEWAY_ID' is not registered. Start gateway_runtime first, then re-run this script."
  exit 1
fi
info "Gateway '$GATEWAY_ID' found."

# ── 3. Check if a pipeline already exists for this gateway ───────────────────
info "Checking for existing pipelines ..."
PIPELINES=$(_get "/api/v1/pipelines")
EXISTING_PIPELINE_ID=$(echo "$PIPELINES" | python3 -c "
import sys, json
pipelines = json.load(sys.stdin)
match = next((p for p in pipelines if p['gateway_id'] == '$GATEWAY_ID'), None)
print(match['id'] if match else '')
")

if [[ -n "$EXISTING_PIPELINE_ID" ]]; then
  warn "Pipeline already exists for '$GATEWAY_ID' (id=$EXISTING_PIPELINE_ID). Skipping pipeline creation."
  PIPELINE_ID="$EXISTING_PIPELINE_ID"
else
  # ── 4. Create the pipeline ──────────────────────────────────────────────────
  info "Creating pipeline for '$GATEWAY_ID' ..."
  PIPELINE_PAYLOAD=$(python3 -c "
import json
payload = {
    'name': 'demo-pipeline',
    'gateway_id': '$GATEWAY_ID',
    'config': {
        'adapters': [
            {
                'adapter_id': 'modbus-demo-01',
                'adapter_type': 'modbus_tcp',
                'config': {
                    'host': 'modbus-simulator',
                    'port': 5020,
                    'unit_id': 1,
                    'poll_interval_ms': 1000,
                    'registers': [
                        {'address': 40001, 'param': 'temperature', 'type': 'float32', 'unit': 'celsius'}
                    ],
                    'output': {
                        'kafka_bootstrap': 'kafka:9092',
                        'topic': 'telemetry.raw',
                        'asset_id': 'demo_sensor_01'
                    }
                }
            }
        ],
        'validation': {
            'enabled': True,
            'raw_topic': 'telemetry.raw',
            'clean_topic': 'telemetry.clean',
            'dlq_topic': 'dlq.telemetry',
            'ranges': {
                'temperature': {'min': -50, 'max': 500}
            },
            'rate_of_change': {
                'temperature': 20
            },
            'gap_detection': {
                'temperature': 5
            }
        }
    }
}
print(json.dumps(payload))
")

  PIPELINE_RESP=$(_post "/api/v1/pipelines" "$PIPELINE_PAYLOAD")
  PIPELINE_ID=$(echo "$PIPELINE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  info "Pipeline created (id=$PIPELINE_ID)."
fi

# ── 5. Check if a sink already exists for this pipeline ──────────────────────
info "Checking for existing sinks on pipeline $PIPELINE_ID ..."
SINKS=$(_get "/api/v1/sinks")
EXISTING_SINK=$(echo "$SINKS" | python3 -c "
import sys, json
sinks = json.load(sys.stdin)
match = next((s for s in sinks if s['pipeline_id'] == $PIPELINE_ID), None)
print(match['id'] if match else '')
")

if [[ -n "$EXISTING_SINK" ]]; then
  warn "Sink already exists for pipeline $PIPELINE_ID (id=$EXISTING_SINK). Skipping sink creation."
else
  # ── 6. Create the sink ───────────────────────────────────────────────────────
  info "Creating TimescaleDB sink for pipeline $PIPELINE_ID ..."
  SINK_PAYLOAD=$(python3 -c "
import json
payload = {
    'pipeline_id': $PIPELINE_ID,
    'sink_type': 'timescaledb',
    'status': 'active',
    'config': {
        'kafka_bootstrap': 'kafka:9092',
        'topic': 'telemetry.clean',
        'group_id': 'sf-sink-timescaledb',
        'db_dsn': 'postgresql://streamforge:streamforge@timescaledb:5432/streamforge',
        'table': 'telemetry_clean'
    }
}
print(json.dumps(payload))
")

  SINK_RESP=$(_post "/api/v1/sinks" "$SINK_PAYLOAD")
  SINK_ID=$(echo "$SINK_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  info "Sink created (id=$SINK_ID)."
fi

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
info "Done. Demo topology is seeded:"
info "  Gateway  : $GATEWAY_ID"
info "  Pipeline : $PIPELINE_ID (modbus-demo-01 → telemetry.raw → validator → telemetry.clean)"
info "  Sink     : TimescaleDB (telemetry.clean → timescaledb:5432/streamforge.telemetry_clean)"
echo ""
warn "If gateway_runtime is already running, it will pick up the new config within GATEWAY_POLL_INTERVAL seconds (default 30s)."
warn "Or restart it now: docker compose -f docker-compose.dev.yml restart gateway_runtime"
