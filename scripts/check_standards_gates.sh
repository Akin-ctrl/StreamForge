#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

failures=0

print_section() {
  printf '\n[%s]\n' "$1"
}

report_failure() {
  local description="$1"
  local output="$2"
  printf 'FAIL: %s\n' "$description"
  printf '%s\n' "$output"
  failures=$((failures + 1))
}

report_success() {
  local description="$1"
  printf 'PASS: %s\n' "$description"
}

check_no_matches() {
  local description="$1"
  local pattern="$2"
  shift 2

  local output
  local status
  set +e
  output="$(rg -n --pcre2 "$pattern" "$@" 2>&1)"
  status=$?
  set -e

  if [[ $status -eq 0 ]]; then
    report_failure "$description" "$output"
    return
  fi

  if [[ $status -eq 1 ]]; then
    report_success "$description"
    return
  fi

  printf 'ERROR: %s\n%s\n' "$description" "$output"
  exit "$status"
}

print_section "Runtime Logging Discipline"
check_no_matches \
  "runtime and adapter production modules must not use raw print(...)" \
  '^\s*print\s*\(' \
  gateway_runtime adapters sinks \
  --glob '*.py' \
  --glob '!**/tests/**' \
  --glob '!**/__pycache__/**'

print_section "Security Defaults"
check_no_matches \
  "weak auth/default credential strings must not appear in app or deploy sources" \
  'change-me|admin123|streamforge-dev-secret' \
  control-plane/app deploy control-plane/README.md README.md \
  --glob '!control-plane/app/core/security.py' \
  --glob '!**/__pycache__/**'

print_section "UI Typing Discipline"
check_no_matches \
  "ui/src must not regress to any/as any/Record<string, any>" \
  '\bany\b|as any|Record<string,\s*any>' \
  ui/src \
  --glob '*.{ts,tsx}'

if [[ $failures -gt 0 ]]; then
  printf '\nStandards gate checks failed: %d issue(s) found.\n' "$failures"
  exit 1
fi

printf '\nAll standards gate checks passed.\n'
