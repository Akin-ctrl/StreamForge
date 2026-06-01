#!/usr/bin/env bash
# seed_dev.sh - Local-demo convenience wrapper.
#
# Production-like verification should use gateway enrollment, operator approval,
# and UI/API configuration. This script intentionally delegates to the maintained
# dev_bootstrap.py path so local demo seeding has a single implementation.
#
# Usage:
#   ./seed_dev.sh [CONTROL_PLANE_URL]
#
# Defaults to http://localhost:8001 if no argument is given.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="${1:-http://localhost:8001}"

export CONTROL_PLANE_URL="$BASE_URL"
export CONTROL_PLANE_GATEWAY_ID="${CONTROL_PLANE_GATEWAY_ID:-gateway-demo-01}"
export DEV_ADMIN_USERNAME="${DEV_ADMIN_USERNAME:-streamforge_admin}"
export DEV_ADMIN_PASSWORD="${DEV_ADMIN_PASSWORD:-LocalAdminBootstrap42}"
export DEV_GATEWAY_CONFIG_PATH="${DEV_GATEWAY_CONFIG_PATH:-$SCRIPT_DIR/gateway_config.sample.json}"

echo "[seed] Local-demo bootstrap only. Production-like installs should use gateway enrollment and approval."
python3 "$SCRIPT_DIR/dev_bootstrap.py"
echo "[seed] Done. Demo topology seeded for $CONTROL_PLANE_GATEWAY_ID at $CONTROL_PLANE_URL."
