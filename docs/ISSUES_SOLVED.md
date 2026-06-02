# StreamForge Resolved Issues Ledger

This file tracks issues that have been completed and moved out of active queues.

Last updated: 2026-05-30

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
| Publishing behavior not centralized | ✅ Solved | Added shared adapter Kafka-compatible publisher and schema serializer path. | `adapters/adapter_base/kafka_publisher.py`, `adapters/adapter_base/schema.py` |
| Modbus polling/retry gaps | ✅ Solved | Added contiguous batching + retry/backoff/reconnect behavior. | `adapters/adapter_modbus_tcp/modbus_tcp_adapter.py` |
| Runtime-managed embedded broker lifecycle gap | ✅ Solved | Added local Kafka-compatible broker auto-manage/supervision in runtime manager. | `gateway_runtime/kafka_manager.py` |
| Redpanda local broker migration | ✅ Solved for local dev/runtime | Dev compose now uses pinned Redpanda, runtime broker management is Redpanda-first with a Confluent fallback, and schema compatibility was verified against Redpanda Schema Registry. Production packaging remains open. | `deploy/dev/docker-compose.yml`, `gateway_runtime/kafka_manager.py`, `gateway_runtime/tests/test_kafka_manager.py`, `schemas/telemetry.avsc`, `adapters/tests/test_schema_manager.py` |
| Control-plane config cache semantics gap | ✅ Solved | Added cache-first startup + refresh + cache persistence behavior. | `gateway_runtime/config.py`, `gateway_runtime/runtime.py` |
| Explicit circuit breaker strategy gap | ✅ Solved | Added reusable circuit breaker + runtime/control-plane/sink integration. | `gateway_runtime/circuit_breaker.py`, `gateway_runtime/config.py`, `sinks/sink_timescaledb/main.py` |
| Validator offset durability gap | ✅ Solved | Validator now commits Kafka offsets only after clean-topic/DLQ durability. | `gateway_runtime/validator.py` |
| Sink SQL identifier safety gap | ✅ Solved | TimescaleDB sink validates and safely renders configured table identifiers. | `sinks/sink_timescaledb/main.py` |
| Gateway status/approval consistency gap | ✅ Solved | Gateway update paths now reconcile and enforce `status`/`approved` invariants server-side. | `control-plane/app/routers/gateways.py` |

---

## Resolved from Runtime Architecture Review (2026-05)

| Issue | Status | Resolution Summary | Evidence |
|------|--------|--------------------|----------|
| Validator execution path under-isolated | ✅ Solved | Refactored validator into staged in-process workers instead of one long loop. | `gateway_runtime/validator.py` |
| No bounded internal stage handoff | ✅ Solved | Added bounded ingress/publish/completion queues between validator stages. | `gateway_runtime/validator.py` |
| No explicit runtime backpressure state | ✅ Solved (baseline) | Added queue saturation handling, blocked counters, and explicit backpressure reporting. | `gateway_runtime/validator.py`, `gateway_runtime/runtime.py` |
| No per-stage runtime observability | ✅ Solved | Added per-stage counters, latency metrics, queue depth, emit totals, and health snapshots. | `gateway_runtime/validator.py`, `gateway_runtime/runtime.py` |
| Health UI too shallow for validator pipeline visibility | ✅ Solved | Health UI now shows validator queues, stage states, and backpressure details. | `ui/src/features/health/HealthPage.tsx` |
| Missing in-runtime aggregator and aggregate topics | ✅ Solved | Added gateway-local aggregator module with Avro aggregate publishing to `telemetry.1s` and `telemetry.1min`, plus runtime health and metrics exposure. | `gateway_runtime/aggregator.py`, `gateway_runtime/runtime.py`, `schemas/telemetry_aggregate.avsc` |
| Aggregate topics were not persisted to TimescaleDB | ✅ Solved | Added explicit TimescaleDB sink support for aggregate payloads and wired separate sink configs for `telemetry.1s` and `telemetry.1min`. | `sinks/sink_timescaledb/main.py`, `deploy/dev/gateway_config.sample.json` |
| Aggregate window rows duplicated on restart/replay | ✅ Solved | Aggregate tables now dedupe historical duplicate windows, enforce a unique window key, and upsert by `(asset_id, parameter, window_start, window_end)`. | `sinks/sink_timescaledb/main.py`, `sinks/tests/test_sink_timescaledb.py` |
| Managed adapter startup depended on missing dedicated dev image | ✅ Solved | Adapter manager now launches adapters with explicit commands and configurable image selection compatible with the dev stack. | `gateway_runtime/adapter_manager.py`, `deploy/dev/docker-compose.yml` |
| Fresh-stack end-to-end verification gaps | ✅ Solved | Live stack was revalidated from Modbus simulator through the Redpanda-backed local stream, validator, alarms/DLQ, and TimescaleDB. | `deploy/dev/docker-compose.yml`, `gateway_runtime/validator.py`, `sinks/sink_timescaledb/main.py` |
| UI/control-plane startup race caused signup-time 502s | ✅ Solved | UI now waits for `control_plane` health instead of mere process start. | `deploy/dev/docker-compose.yml` |
| Overflow admin actions failed against external Compose broker | ✅ Solved | Local broker container discovery now resolves Compose service/alias-backed Kafka-compatible containers correctly for overflow admin operations. | `gateway_runtime/kafka_manager.py`, `gateway_runtime/tests/test_kafka_manager.py` |
| Overflow evict stage failed when aggregate topics were absent | ✅ Solved | Optional aggregate-topic retention updates are now tolerated until the aggregate topics exist. | `gateway_runtime/overflow.py`, `gateway_runtime/tests/test_overflow.py` |
| Overflow recovery left stale topic overrides after restart | ✅ Solved | Overflow now restores local stream topic defaults on first normal evaluation after restart, not only on an in-process stage transition. | `gateway_runtime/overflow.py`, `gateway_runtime/tests/test_overflow.py` |

---

## Resolved from PROJECT_PHASES Historical Queue

| Historical Queue Item | Status | Resolution Summary |
|-----------------------|--------|--------------------|
| Control-plane startup robustness for token/config fetch | ✅ Solved | Token refresh/retry + cache-first startup implemented. |
| Health signal validation completeness (baseline hardening) | ✅ Solved (baseline) | Component health endpoints/reporting added; deeper production SLO validation remains future work. |
| Config cache behavior under control-plane outage | ✅ Solved | Deterministic cache startup and fallback behavior implemented. |
| Dev-stack parity guardrails (baseline) | ✅ Solved (baseline) | Single-node Redpanda/Kafka-compatible dev constraints are codified in compose/runtime settings. |

---

## Resolved from UI Product Roadmap (2026-05)

| Roadmap Item | Status | Resolution Summary | Evidence |
|-------------|--------|--------------------|----------|
| UI information architecture correction | ✅ Solved | Reframed the UI around Overview, Fleet, Gateways, Adapters, Deployments, Sinks, and operator operations views. | `ui/src/App.tsx`, `ui/src/app/layout/AppShell.tsx` |
| First-class adapters section | ✅ Solved | Added persisted adapter inventory/management and protocol-aware authoring flows. | `ui/src/features/adapters/`, `control-plane/app/routers/adapters.py` |
| Deployment/composition builder rework | ✅ Solved | Deployments now compose saved adapters and sinks rather than hiding everything inside one mixed wizard. | `ui/src/features/pipelines/`, `control-plane/app/routers/deployments.py` |
| Object ownership and reuse clarity | ✅ Solved | Adapter/sink reuse and deployment composition are now explicit across pages, summaries, and review panels. | `ui/src/features/adapters/`, `ui/src/features/sinks/`, `ui/src/features/pipelines/` |
| Connection test and preflight UX | ✅ Solved | Added adapter/sink validation and test-connection actions plus deployment preflight checks. | `control-plane/app/core/operator_checks.py`, `control-plane/app/core/connection_tests.py`, `ui/src/shared/forms/ActionResultPanel.tsx` |
| Event and aggregate UX | ✅ Solved | Added operator-facing event and aggregate inventory/detail views backed by control-plane read APIs. | `ui/src/features/events/EventsPage.tsx`, `ui/src/features/aggregates/AggregatesPage.tsx`, `control-plane/app/routers/events.py`, `control-plane/app/routers/aggregates.py` |
| Fleet operations and topology views | ✅ Solved | Added fleet inventory, gateway drill-down, and topology visibility surfaces. | `ui/src/features/fleet/`, `ui/src/shared/fleet/` |
| Logs viewer | ✅ Solved | Added real gateway-runtime log transport through heartbeat state and surfaced it in control-plane/UI logs views. | `gateway_runtime/logging_utils.py`, `control-plane/app/routers/logs.py`, `ui/src/features/logs/LogsPage.tsx` |

---

## Remaining Open Work

Open items are tracked in:

- `PROJECT_PHASES.md` (Active Issue Queue)
- `docs/adr/ADR-011-phase-1-4-conformance-baseline.md` (P2/P3 open checkboxes)
- `docs/UI_PRODUCT_ACTION_LIST.md` (current UI/product roadmap)
- `docs/PRODUCTION_READINESS_RECONCILIATION.md` (reconciled trust blockers, outdated review findings, and before-AI exit criteria)
