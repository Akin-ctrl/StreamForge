# ADR-011: Phase 1-4 Architecture Conformance Baseline

**Status**: Accepted  
**Date**: 2026-03-28  
**Decision**: Adopt a formal Phase 1-4 conformance baseline and use it as the source of truth for remediation planning.

---

## Context

During Phase 4 implementation work, architecture drift concerns were raised. A full documentation and code audit was performed across:

- Root and system docs (`README.md`, `PROJECT_PHASES.md`, `docs/ARCHITECTURE.md`, `docs/DATA_FLOW.md`, `docs/DEPLOYMENT.md`, `docs/SECURITY.md`)
- ADRs (`ADR-001` to `ADR-010`)
- Runtime, control-plane, adapters, sinks, deploy, and UI implementation

This ADR records what is currently aligned vs omitted for Phases 1-4 and defines a baseline for closing gaps.

---

## Decision

1. The findings in this ADR are the **official conformance baseline** for Milestones/Phases 1-4.
2. Work planning after this date must reference this ADR when claiming architecture compliance.
3. Any closure of a listed omission must include:
   - code implementation,
   - docs update,
   - and explicit reference back to this ADR section.

---

## Conformance Findings

### Phase 1: Core Foundation

#### Followed
- Modbus TCP adapter implemented and publishing normalized telemetry.
- Local Kafka dependency wired and health-checked by runtime.
- Core schema files exist (`telemetry`, `event`, `alarm`).
- Dev compose stack exists for local demo/development.

#### Omitted / Partial
- Runtime does not manage embedded Kafka lifecycle; it only waits for reachability.
- Adapter runtime support is effectively single-protocol (`modbus_tcp`) while architecture describes broader protocol set.

---

### Phase 2: Control Plane API

#### Followed
- Gateway registration, approval, token issue/renew, and gateway config endpoint exist.
- Pipeline CRUD and Sink CRUD exist.
- User auth (JWT) and admin checks are implemented.

#### Omitted / Partial
- Runtime does not fully auto-register itself if missing; token request path assumes pre-registration.
- Control-plane config cache semantics for deterministic offline startup/fallback are not fully implemented as documented autonomy behavior.

---

### Phase 3: Validation & Sinks

#### Followed
- Validator module runs in gateway runtime (not containerized) with quality outcomes and DLQ emission.
- Sink manager lifecycle exists for sink containers.
- TimescaleDB sink implementation exists and writes validated telemetry.

#### Omitted / Partial
- Operator DLQ workflow (view, approve/reprocess, discard) is not implemented in control-plane API/UI.
- Sink portfolio in architecture/ADR is broader than current implementation.

---

### Phase 4: UI

#### Followed
- Login/auth guard routing is implemented.
- Gateway and Health views are implemented.
- Pipeline Builder flow exists and compiles backend payload.

#### Omitted / Partial
- Alarm view and DLQ view required by milestone scope are not implemented.
- Backend alarm endpoints are also missing, blocking corresponding UI completion.

---

## ADR-Level Drift Summary

### ADR-001 (Edge Buffering)
- **Partial**: Local Kafka pattern exists, but runtime lifecycle control and advanced buffering controls are limited.

### ADR-002 (Protocol Adapters)
- **Partial**: Containerized adapter pattern exists; runtime support remains effectively single-adapter type.

### ADR-003 (Schema Management)
- **Not aligned**: Docs/ADR specify Avro + Schema Registry + offline schema cache; implementation path is primarily JSON serialization with local JSON schema validation.

### ADR-004 (Validation & DLQ)
- **Partial**: Validation and DLQ routing exist; operator DLQ workflows are missing.

### ADR-005 (Sink Architecture)
- **Partial**: Containerized sink pattern implemented; sink catalog scope remains limited in practice.

### ADR-006 (Gateway Autonomy)
- **Partial**: Polling/backoff behavior exists; deterministic cached config behavior for offline continuity remains incomplete.

### ADR-007 (Authentication)
- **Partial**: Gateway/user JWT implemented; broader enterprise path (OAuth/OIDC, richer RBAC model) is not complete.

### ADR-008 (Failure Modes)
- **Partial**: Basic restart/degradation behavior present; explicit circuit breaker strategy is not fully implemented.

### ADR-009 (Overflow Handling)
- **Not aligned**: Tiered overflow controls (compress/downsample/priority eviction/block) are not implemented.

### ADR-010 (Copilot/MCP)
- **Not aligned for Phase 1-4 scope**: No implemented MCP tool surface matching ADR intent.

---

## Architecture Documentation Drift

There is a documentation inconsistency around central Kafka language:

- Some architecture text states StreamForge manages only local gateway Kafka.
- Some data-flow/deployment sections still describe central Kafka patterns in a way that can be interpreted as platform-managed.

This must be reconciled to avoid conflicting implementation direction.

---

## Consequences

### Positive
- Team now has an explicit, versioned baseline of what is done vs missing.
- Future claims of “architecture complete” can be validated against concrete criteria.

### Negative
- Existing progress narratives may need correction where they over-claimed phase completion.

---

## Required Follow-up

1. Create a remediation backlog mapped to this ADR (P1/P2/P3 priorities).
2. Close Phase 4 scope gaps first (Alarms + DLQ APIs/UI).
3. Decide and codify final direction for:
   - schema strategy (Avro+Registry vs current JSON path),
   - gateway autonomy cache semantics,
   - overflow handling implementation.
4. Reconcile architecture docs for local-vs-central Kafka ownership language.

---

## Related ADRs

- [ADR-001](ADR-001-edge-buffering.md)
- [ADR-002](ADR-002-protocol-adapters.md)
- [ADR-003](ADR-003-schema-management.md)
- [ADR-004](ADR-004-validation-dlq.md)
- [ADR-005](ADR-005-sink-architecture.md)
- [ADR-006](ADR-006-gateway-autonomy.md)
- [ADR-007](ADR-007-authentication.md)
- [ADR-008](ADR-008-failure-modes.md)
- [ADR-009](ADR-009-overflow-handling.md)
- [ADR-010](ADR-010-copilot-mcp.md)
