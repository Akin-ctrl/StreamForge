# StreamForge Production Readiness Reconciliation

This document reconciles recent external industry-style reviews against the
current codebase and the implementation history as of `2026-05-30`.

It exists to separate:

- issues that are still real and should block production trust
- issues that are partially addressed but still need hardening
- review findings that are now outdated because the codebase has moved forward

This file is not a marketing roadmap. It is a practical trust-and-delivery
document intended to keep architecture, implementation, and operator
expectations aligned.

---

## Current Bottom Line

StreamForge now has a credible implemented core:

- reusable adapters
- reusable sinks
- composed deployments
- adapter/sink validation and connection testing
- deployment preflight
- events, aggregates, fleet, and logs operator views
- DLQ and alarm surfaces
- route, runtime, adapter, sink, and browser-level regression coverage

The edge stream backbone is now aligned around Redpanda for the local
dev/runtime path. The platform still uses Kafka-compatible clients, topics,
offsets, and consumer groups, but the embedded broker direction is Redpanda.
Production packaging and image-pull templates are still pending.

The remaining gap is not whether the platform has a coherent architecture. It
does. The remaining gap is whether the platform has enough operational trust,
field verification, and documentation fidelity to deserve production-scale and
AI-assisted workflows on top of it.

---

## A. Still Open: Production-Trust Blockers

These are the most important unresolved items.

### 0. Redpanda production packaging and hardening

Current shipped behavior:

- the development stack uses `redpandadata/redpanda:v26.1.9`
- the runtime-managed broker path is Redpanda-first with a Confluent fallback
- application code uses Kafka-compatible producers, consumers, topics, offsets,
  and consumer groups
- Avro schema registration has been verified against Redpanda's Schema Registry
- the local stack has been verified end-to-end into TimescaleDB

Why this matters:

- Redpanda better matches StreamForge's edge-first positioning
- production installation should not depend on ad hoc local compose assumptions
- broker storage, retention, and recovery behavior still need field-level
  packaging decisions

Open work:

- publish and pin production gateway/runtime images
- provide image-pull templates instead of hand-written production manifests
- document production Redpanda sizing, retention, TLS, backup, and recovery
- keep Kafka-compatible client semantics and topic contracts intact

### 1. Gateway onboarding and approval UX

Current shipped behavior:

- gateway self-registration remains disabled
- admin-managed enrollment tokens are now available
- gateways can enroll as pending by presenting an enrollment token
- operators can approve pending gateways from the UI
- the gateway runtime enrollment path has been verified against the live dev
  stack using the real control-plane repository code path
- local compose can pass enrollment identity/token environment variables without
  changing the default demo-gateway behavior
- a clean local stack has been verified from first-admin bootstrap through
  enrollment-token creation, runtime enrollment, approval, deployment preflight,
  active deployment creation, Redpanda topics/schemas, and TimescaleDB telemetry
  landing without `dev_bootstrap`
- manual gateway creation remains available for controlled environments and
  local development

Why this matters:

- multi-site deployments need a realistic way for gateways in remote locations
  to appear in the control plane in a manageable, reviewable state
- enrollment makes central and site-local deployments follow the same operator
  model

Open work:

- document connected and site-local installation runbooks after packaging exists
- decide whether one-time gateway-specific claim tokens are needed in addition
  to site/install tokens

### 2. Physical-device verification from the gateway side

Current shipped behavior:

- control-plane-side validation and reachability probes still exist
- saved adapters and sinks can now request gateway-executed connection tests
- the gateway runtime polls for pending tests, executes them from the gateway
  network, and posts structured pass/fail/unsupported results back to the
  control plane
- the UI exposes gateway-side tests for saved adapters and sinks attached to a
  gateway deployment
- the live clean-stack verification proved gateway-side Modbus TCP reachability
  to the local simulator and gateway-side TimescaleDB sink reachability

Why this matters:

- industrial trust requires proving real device access, not only central
  control-plane reachability
- this is especially important for Modbus RTU, remote Modbus TCP, OPC UA, and
  site-local broker/device paths

Open work:

- verify the same gateway-side test path against real physical devices, not only
  local simulator/container endpoints
- deepen protocol-aware probes where needed, such as reading a configured Modbus
  register range instead of only proving a Modbus TCP session
- keep unsupported states honest for Modbus RTU when the gateway has no serial
  device access

### 3. Modbus TCP failure isolation

Current concern:

- the Modbus TCP adapter remains too large and centralizes batching, decode,
  reconnect, and event logic in one place
- one failed register range should not require tearing down the whole session
  if other ranges are still readable

Why this matters:

- real PLCs often degrade partially rather than failing cleanly
- per-batch isolation is important for graceful degradation

Open work:

- isolate per-batch failures more narrowly
- add more explicit per-batch error health signals

### 4. Initial provisioning retry behavior

Current shipped behavior:

- steady-state control-plane config refresh uses exponential backoff
- initial provisioning wait still relies on a fixed retry interval

Why this matters:

- gateways in degraded-connectivity environments should not hammer the control
  plane during first-boot or pending-approval waits

Open work:

- add backoff and jitter to the initial provisioning retry path
- align onboarding retry behavior with the runtime's broader resilience model

### 5. Secret resolution fidelity gap

Current shipped behavior:

- secret fields are modeled and handled safely in the control plane and UI
- `${vault:...}` and `${secret:...}` runtime interpolation is still documented
  more strongly than it is implemented in the gateway runtime

Why this matters:

- production deployments need a truthful, supported secret resolution story
- documentation must not imply Vault-backed runtime behavior that does not yet
  exist

Open work:

- either implement runtime secret resolution properly
- or reduce the docs to match the current shipped behavior

### 6. Fresh-stack and ugly-failure proof

Current shipped behavior:

- the platform has good targeted tests and meaningful live verification
- the full pre-AI production trust gate is not yet formalized and closed

Why this matters:

- the threshold before AI is confidence under restart, replay, outage,
  backpressure, and operator recovery conditions

Open work:

- formalize the clean-stack smoke phase as a repeatable gate
- complete the failure-path matrix
- define and run the pre-AI verification gate consistently

---

## B. Open: Important Hardening Work

These do not all block current use equally, but they still matter before broad
production trust.

### 1. Topology redesign

Current shipped behavior:

- topology exists
- it is operationally useful as a baseline
- it is still box/column oriented rather than clearly flow oriented

Open work:

- redesign the topology as a clearer architecture/DAG-style flow
- make directionality and stage relationships easier to understand at a glance

### 2. Responsive and readability hardening

Current shipped behavior:

- the UI has materially improved
- shared layout and data-display primitives now exist
- the interface still needs more resilience under zoom, larger text, and
  varying screen sizes

Open work:

- harden form layouts, tables, filters, topology, and detail panes across
  screen sizes and text/zoom conditions

### 3. Operator-style end-to-end verification

Current shipped behavior:

- technical verification exists
- a documented operator walkthrough is still missing

Open work:

- define the exact operator E2E flow:
  - onboard gateway
  - approve or enroll it
  - configure adapter and sink
  - validate and test
  - preflight and deploy
  - verify telemetry, logs, fleet, and post-deploy health

### 4. Observability depth

Current shipped behavior:

- health, metrics, logs, and fleet visibility are real
- observability is no longer a blank area

Open work:

- deepen per-stage, per-adapter, and per-sink operational signals where
  necessary
- continue standardizing diagnosability for 2am operator use, not only for
  developers with shell access

### 5. Security/runtime hardening depth

Current shipped behavior:

- RBAC, audit, session hardening, and gateway token paths are materially better
  than the earlier baseline

Open work:

- strengthen auth abuse protection where necessary
- harden long-lived token lifecycle and related operational procedures
- continue verifying that all state-changing actions are fully audit-visible

---

## C. Review Findings That Are Now Outdated

These points were reasonable at an earlier moment, but they are no longer
accurate as written against the current codebase.

### 1. "DLQ backend support is missing"

No longer accurate.

Current codebase includes:

- control-plane DLQ router
- DLQ review, approve, discard, pending gateway action, and completion flows
- UI DLQ workflow

Better current framing:

- DLQ backend exists
- what still needs strengthening is deeper verification, idempotency confidence,
  and broader operational hardening

### 2. "Logs viewer is missing / fake"

No longer accurate.

Current codebase includes:

- gateway-runtime recent log transport
- control-plane logs API
- UI logs page with filtering

Better current framing:

- logs viewer exists
- longer-lived log storage and broader production retention policy remain open

### 3. "Connection test and preflight UX are missing"

No longer accurate.

Current codebase includes:

- adapter validate/test connection actions
- sink validate/test connection actions
- deployment preflight

Better current framing:

- connection/preflight exist
- gateway-side physical-device verification remains open

### 4. "Fleet last-seen / operational visibility are missing"

No longer accurate.

Current codebase includes:

- fleet page
- gateway heartbeat visibility
- last-seen and runtime-health surfaces

Better current framing:

- operational surfaces exist
- they still need topology and diagnosability refinement

### 5. "copilot/ directory is absent"

No longer accurate as a literal repository claim.

The repository now contains a `copilot/` directory.

Better current framing:

- AI/copilot should still be treated as a future or optional capability until
  it has a clearly committed and production-honest scope

### 6. "`fastavro` exists only in gateway runtime requirements"

No longer accurate.

Current codebase includes `fastavro` where needed for the current adapter path.

Better current framing:

- schema behavior still needs hardening and clearer eager validation in some
  places
- but the dependency claim itself is outdated

### 7. "`telemetry.clean` persistence is still unresolved"

No longer accurate.

The primary Timescale sink issue that blocked `telemetry.clean` writes was
identified and fixed. The path now ingests again. What remains is keeping that
path covered by regression and smoke verification.

---

## D. Items That Need Reframing, Not Checkboxing

Some review items should not be treated as "missing yes/no" because the right
question is depth and maturity, not existence.

### 1. DLQ

Question is no longer:

- "Does the DLQ exist?"

Question now is:

- "Is the DLQ flow production-hard enough under replay, duplicate handling, and
  operator recovery conditions?"

### 2. Observability

Question is no longer:

- "Are there health/log/metrics pages?"

Question now is:

- "Are the operational signals sufficient for diagnosis without shell access?"

### 3. Schema handling

Question is no longer:

- "Is there any schema machinery?"

Question now is:

- "How eager, durable, and drift-resistant is the schema path under change and
  outage conditions?"

### 4. Security

Question is no longer:

- "Is there RBAC and session hardening?"

Question now is:

- "Have abuse protection, token lifecycle, and deployment-time operational
  controls been hardened enough for broad production use?"

---

## E. Open Architecture Decisions

These decisions are still being actively discussed and should be resolved
explicitly rather than by drift.

### 1. Gateway onboarding model

Options:

- strict admin pre-creation
- self-registration
- enrollment / claim flow

Current recommendation:

- prefer an enrollment / claim flow as the best balance of field practicality
  and control-plane trust

### 2. Physical-device verification execution model

Options:

- control-plane initiated only
- gateway-executed checks reported back to the control plane/UI

Current recommendation:

- use gateway-executed tests for real device/network verification
- keep control-plane-side tests for central reachability checks

### 3. Topology presentation model

Options:

- operational DAG
- architecture-style flow view
- hybrid model

Current recommendation:

- favor a hybrid that reads like a clear dataflow first and an architecture
  diagram second

---

## F. Before-AI Exit Criteria

The following should be true before AI/copilot becomes an active product
investment layer on top of the operator platform:

- gateway onboarding story is production-honest
- production-like verification no longer depends on local demo seeding
- gateway-side physical-device verification exists
- fresh-stack smoke verification is repeatable
- failure-path matrix is covered
- topology is readable enough to support operator understanding
- docs clearly distinguish shipped behavior from planned behavior
- the current golden path is trusted:
  - source adapter
  - local Kafka-compatible stream
  - validator
  - sink
  - fleet/log/health visibility

---

## G. Recommended Prioritization

### Must do before AI

- Redpanda production packaging and hardening
- physical-device verification on real hardware
- provisioning retry hardening
- Modbus failure isolation
- fresh-stack smoke verification
- failure-path matrix
- documentation fidelity cleanup

### Strongly recommended in the same window

- topology redesign
- responsive/readability hardening
- operator runbook / E2E verification flow
- deeper diagnosability surfaces

### Can remain later or optional

- optional enterprise auth UX
- broader copilot/MCP expansion
- additional non-core adapters and sinks beyond the current focus paths
