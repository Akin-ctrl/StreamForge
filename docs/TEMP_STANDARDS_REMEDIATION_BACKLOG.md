# Temporary Standards Remediation Backlog

This document is temporary.

It now serves as the post-remediation audit tracker for the standards work. It should be deleted once the remaining gaps listed here are resolved and re-audited.

## Audit Snapshot

- Audit date: `2026-05-19`
- Standards baseline: [CODING_STANDARDS_COMMITMENT.md](/home/StreamForge/CODING_STANDARDS_COMMITMENT.md)
- Branch context: `secret-remediation-foundation`

## What Is Now Closed

The following original backlog items are now considered closed:

1. Plaintext secret round-tripping
2. Insecure auth defaults
3. Browser `localStorage` auth token persistence
4. Missing audit trail foundation
5. Missing persisted roles and least-privilege RBAC
6. Backend/frontend contract drift at the canonical schema level
7. Mixed legacy/canonical validation tolerance
8. Weak UI typing
9. Adapter lifecycle inconsistency between bulk-start and single-start
10. Oversized adapter and sink form modules
11. Runtime `print(...)` logging in production paths
12. Missing standards-aligned regression coverage

These were closed through Tracks A to D plus Track E steps 1 and 2.

## Current Verification Status

The current remediation state has direct verification behind it:

- `bash scripts/check_standards_gates.sh` passes
- `python3 -m unittest discover -s gateway_runtime/tests` passes: `70 tests`
- `python3 -m unittest discover -s adapters/tests` passes: `43 tests`
- targeted control-plane regression functions executed successfully in the project venv: `46 tests`

The control-plane project environment still does not have `pytest` installed, so the control-plane regression run currently uses a lightweight local runner instead of `pytest` itself. That is tracked below as a remaining verification gap, not as a hidden success.

## Remaining Confirmed Gaps

### High

1. Broad `except Exception` handling is still too common in runtime, adapter, sink, and support infrastructure code.
- This remains the largest unresolved engineering-discipline issue.
- Some outer containment boundaries are deliberate and acceptable, but many inner catches are still broader than they should be.

Primary files:
- [gateway_runtime/kafka_manager.py](/home/StreamForge/gateway_runtime/kafka_manager.py)
- [gateway_runtime/validator.py](/home/StreamForge/gateway_runtime/validator.py)
- [gateway_runtime/event_validator.py](/home/StreamForge/gateway_runtime/event_validator.py)
- [gateway_runtime/aggregator.py](/home/StreamForge/gateway_runtime/aggregator.py)
- [gateway_runtime/overflow.py](/home/StreamForge/gateway_runtime/overflow.py)
- [adapters/adapter_mqtt/mqtt_adapter.py](/home/StreamForge/adapters/adapter_mqtt/mqtt_adapter.py)
- [adapters/adapter_opcua/opcua_adapter.py](/home/StreamForge/adapters/adapter_opcua/opcua_adapter.py)
- [sinks/sink_alert_router/main.py](/home/StreamForge/sinks/sink_alert_router/main.py)
- [sinks/sink_http/main.py](/home/StreamForge/sinks/sink_http/main.py)
- [sinks/sink_kafka/main.py](/home/StreamForge/sinks/sink_kafka/main.py)
- [sinks/sink_timescaledb/main.py](/home/StreamForge/sinks/sink_timescaledb/main.py)

2. The UI still carries fallback option tables that duplicate backend catalog semantics.
- The core contract ownership is much better now, but several protocol-aware components still restate catalog options locally as fallbacks.
- This is a smaller issue than before, but it is still real drift risk against the single-source-of-truth standard.

Primary files:
- [ui/src/features/adapters/components/ModbusPointsEditor.tsx](/home/StreamForge/ui/src/features/adapters/components/ModbusPointsEditor.tsx)
- [ui/src/features/adapters/components/ModbusRtuConfigSection.tsx](/home/StreamForge/ui/src/features/adapters/components/ModbusRtuConfigSection.tsx)
- [ui/src/features/adapters/components/MqttConfigSection.tsx](/home/StreamForge/ui/src/features/adapters/components/MqttConfigSection.tsx)
- [ui/src/features/adapters/components/OpcuaConfigSection.tsx](/home/StreamForge/ui/src/features/adapters/components/OpcuaConfigSection.tsx)
- [ui/src/features/sinks/components/HttpSinkSection.tsx](/home/StreamForge/ui/src/features/sinks/components/HttpSinkSection.tsx)
- [ui/src/features/sinks/components/AlertRouterSinkSection.tsx](/home/StreamForge/ui/src/features/sinks/components/AlertRouterSinkSection.tsx)

### Medium

3. Internal routing and transport plumbing is reduced, but not fully out of operator-facing advanced forms.
- This is no longer a normal-flow issue.
- It remains a design and safety concern in advanced sections, where internal Kafka bootstrap, source topic, consumer group, and telemetry topic fields are still directly editable.

Primary files:
- [ui/src/features/sinks/components/TimescaleSinkSection.tsx](/home/StreamForge/ui/src/features/sinks/components/TimescaleSinkSection.tsx)
- [ui/src/features/sinks/components/AlertRouterSinkSection.tsx](/home/StreamForge/ui/src/features/sinks/components/AlertRouterSinkSection.tsx)
- [ui/src/features/adapters/components/OpcuaConfigSection.tsx](/home/StreamForge/ui/src/features/adapters/components/OpcuaConfigSection.tsx)

4. The new standards gate is present, but it is not yet wired into automated CI or a top-level project task runner.
- The repository now has an explicit enforcement script.
- There is still no `.github/workflows` pipeline or equivalent repo-level automation to run it automatically.

Primary files:
- [scripts/check_standards_gates.sh](/home/StreamForge/scripts/check_standards_gates.sh)
- [README.md](/home/StreamForge/README.md)

5. Control-plane regression execution is still more fragile than it should be.
- The control-plane local venv and running container do not currently include `pytest`.
- The tests themselves exist and pass, but the default developer path for running them is not as smooth or explicit as it should be.

Primary files:
- [control-plane/requirements.txt](/home/StreamForge/control-plane/requirements.txt)
- [control-plane/tests/test_secrets.py](/home/StreamForge/control-plane/tests/test_secrets.py)
- [control-plane/tests/test_settings_security.py](/home/StreamForge/control-plane/tests/test_settings_security.py)
- [control-plane/tests/test_auth_session.py](/home/StreamForge/control-plane/tests/test_auth_session.py)
- [control-plane/tests/test_audit.py](/home/StreamForge/control-plane/tests/test_audit.py)
- [control-plane/tests/test_rbac.py](/home/StreamForge/control-plane/tests/test_rbac.py)
- [control-plane/tests/test_config_validation.py](/home/StreamForge/control-plane/tests/test_config_validation.py)
- [control-plane/tests/test_catalog_contracts.py](/home/StreamForge/control-plane/tests/test_catalog_contracts.py)

## Status By Original Backlog Item

- Item 1: closed
- Item 2: closed
- Item 3: closed
- Item 4: closed
- Item 5: closed
- Item 6: mostly closed, with residual UI fallback duplication
- Item 7: closed
- Item 8: partially closed, with residual advanced-form plumbing exposure
- Item 9: closed
- Item 10: open in the broader runtime/adapter/sink surface
- Item 11: closed
- Item 12: closed
- Item 13: closed
- Item 14: closed enough for current scope
- Item 15: closed
- Item 16: partially closed, because enforcement is present but not automated
- Item 17: complete as an audit pass, but this file stays until the remaining gaps above are resolved

## Recommended Next Order

1. Narrow broad exception handling in runtime, adapter, sink, and support infrastructure modules
2. Remove local fallback option tables from UI protocol components so catalog metadata remains authoritative
3. Decide which advanced routing/transport fields should remain editable versus admin-only or fully system-managed
4. Wire the standards gate into an automated project entry point or CI workflow
5. Make control-plane regression execution first-class for developers

## Delete Condition

Delete this file only when:

- the remaining confirmed gaps above are resolved
- the standards gate still passes
- the test matrix still passes
- a final audit finds no remaining confirmed backlog items worth tracking separately
