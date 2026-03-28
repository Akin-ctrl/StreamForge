# StreamForge Resolved Issues Ledger

This file tracks issues that have been completed and moved out of active queues.

Last updated: 2026-03-28

---

## Resolved from ADR-011 (P1/P2)

| Issue | Status | Resolution Summary | Evidence |
|------|--------|--------------------|----------|
| Backend alarm endpoints missing | ✅ Solved | Added alarm ingest/list/get/acknowledge/suppress APIs. | `control-plane/app/routers/alarms.py` |
| Alarm UI missing | ✅ Solved | Added operator alarm page with filters and acknowledge/suppress actions. | `ui/src/features/alarms/AlarmsPage.tsx` |
| Operator DLQ workflow missing in API | ✅ Solved | Added DLQ ingest/review/approve/discard/gateway-action completion workflow APIs. | `control-plane/app/routers/dlq.py` |
| DLQ UI missing | ✅ Solved | Added DLQ review/actions page with filtering and bulk approve. | `ui/src/features/dlq/DlqPage.tsx` |
| First-user bootstrap missing | ✅ Solved | Added bootstrap status + first-user endpoint and UI flow integration. | `control-plane/app/routers/auth.py`, `ui/src/features/auth/LoginPage.tsx` |
| Weak bootstrap credentials posture | ✅ Solved | Added dev-only bootstrap guardrails and stronger password validation path. | `control-plane/app/core/settings.py`, `control-plane/app/core/security.py` |
| Runtime token refresh robustness | ✅ Solved | Added token refresh/retry behavior for control-plane config operations. | `gateway_runtime/config.py` |
| Schema migration maturity gap | ✅ Solved | Added Alembic migration flow and startup schema readiness path. | `control-plane/migrations/`, `control-plane/app/db/schema.py` |
| BaseAdapter lifecycle not structurally enforced | ✅ Solved | Implemented concrete lifecycle template (`run`, `run_once`, graceful shutdown). | `adapters/adapter_base/base_adapter.py` |
| Publishing behavior not centralized | ✅ Solved | Added shared adapter Kafka publisher and schema serializer path. | `adapters/adapter_base/kafka_publisher.py`, `adapters/adapter_base/schema.py` |
| Modbus polling/retry gaps | ✅ Solved | Added contiguous batching + retry/backoff/reconnect behavior. | `adapters/adapter_modbus_tcp/modbus_tcp_adapter.py` |
| Runtime-managed embedded Kafka lifecycle gap | ✅ Solved | Added local Kafka auto-manage/supervision in runtime manager. | `gateway_runtime/kafka_manager.py` |
| Control-plane config cache semantics gap | ✅ Solved | Added cache-first startup + refresh + cache persistence behavior. | `gateway_runtime/config.py`, `gateway_runtime/runtime.py` |
| Explicit circuit breaker strategy gap | ✅ Solved | Added reusable circuit breaker + runtime/control-plane/sink integration. | `gateway_runtime/circuit_breaker.py`, `gateway_runtime/config.py`, `sinks/sink_timescaledb/main.py` |

---

## Resolved from PROJECT_PHASES Historical Queue

| Historical Queue Item | Status | Resolution Summary |
|-----------------------|--------|--------------------|
| Control-plane startup robustness for token/config fetch | ✅ Solved | Token refresh/retry + cache-first startup implemented. |
| Health signal validation completeness (baseline hardening) | ✅ Solved (baseline) | Component health endpoints/reporting added; deeper production SLO validation remains future work. |
| Config cache behavior under control-plane outage | ✅ Solved | Deterministic cache startup and fallback behavior implemented. |
| Dev-stack parity guardrails (baseline) | ✅ Solved (baseline) | Single-node Kafka dev constraints are codified in compose/runtime settings. |

---

## Remaining Open Work

Open items are tracked in:

- `PROJECT_PHASES.md` (Active Issue Queue)
- `docs/adr/ADR-011-phase-1-4-conformance-baseline.md` (P2/P3 open checkboxes)
