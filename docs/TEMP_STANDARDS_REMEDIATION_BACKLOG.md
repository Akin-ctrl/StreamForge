# Temporary Standards Remediation Backlog

This document is temporary.

It exists to track the currently confirmed violations of the repository engineering standards and the ordered remediation plan.

Once the issues listed here have been resolved and re-audited, this file should be deleted.

## Scope

This backlog is based on:
- [CODING_STANDARDS_COMMITMENT.md](/home/StreamForge/CODING_STANDARDS_COMMITMENT.md)
- the expanded software engineering, security engineering, and industrial / OT engineering standards now captured there
- a production-level review of the current control-plane, runtime, adapter, sink, and UI code paths

## External Baselines

The strengthened standards align with the expectations of:
- NIST Secure Software Development Framework (SSDF)
- OWASP ASVS
- CISA Secure by Design
- NIST OT / ICS security guidance
- ISA / IEC 62443 industrial cybersecurity expectations

These references are not reproduced here, but they inform the seriousness and direction of the remediation work.

## Confirmed Issues

### Critical

1. Plaintext secrets are still persisted, returned, and re-exposed through normal CRUD and UI flows.
- Secrets are stored directly in adapter and sink config records.
- The APIs return those records without redaction.
- The UI rehydrates those values into editable form state and JSON fallbacks.

Primary files:
- [models.py](/home/StreamForge/control-plane/app/db/models.py)
- [adapters.py](/home/StreamForge/control-plane/app/routers/adapters.py)
- [sinks.py](/home/StreamForge/control-plane/app/routers/sinks.py)
- [adapterForm.ts](/home/StreamForge/ui/src/features/adapters/adapterForm.ts)
- [sinkForm.ts](/home/StreamForge/ui/src/features/sinks/sinkForm.ts)

2. Secure defaults are not enforced in authentication and session handling.
- The control plane still has unsafe auth-related defaults.
- The UI stores bearer tokens in browser `localStorage`.

Primary files:
- [settings.py](/home/StreamForge/control-plane/app/core/settings.py)
- [main.py](/home/StreamForge/control-plane/app/main.py)
- [session.ts](/home/StreamForge/ui/src/shared/auth/session.ts)

3. There is no real audit trail for operationally significant changes.
- Deployments, adapters, sinks, and gateway approvals do not capture enough actor metadata.
- The system cannot reliably answer who changed what, when, and why.

Primary files:
- [models.py](/home/StreamForge/control-plane/app/db/models.py)
- [deployments.py](/home/StreamForge/control-plane/app/routers/deployments.py)
- [adapters.py](/home/StreamForge/control-plane/app/routers/adapters.py)
- [sinks.py](/home/StreamForge/control-plane/app/routers/sinks.py)
- [gateways.py](/home/StreamForge/control-plane/app/routers/gateways.py)

4. Sensitive infrastructure values are treated as ordinary UI fields.
- Passwords, webhook targets, and DB connection values are surfaced directly in normal authoring and review paths.

Primary files:
- [MqttConfigSection.tsx](/home/StreamForge/ui/src/features/adapters/components/MqttConfigSection.tsx)
- [OpcuaConfigSection.tsx](/home/StreamForge/ui/src/features/adapters/components/OpcuaConfigSection.tsx)
- [TimescaleSinkSection.tsx](/home/StreamForge/ui/src/features/sinks/components/TimescaleSinkSection.tsx)
- [SinkReviewPanel.tsx](/home/StreamForge/ui/src/features/sinks/components/SinkReviewPanel.tsx)

### High

5. Core runtime modules still use `print(...)` instead of structured logging.

Primary files:
- [runtime.py](/home/StreamForge/gateway_runtime/runtime.py)
- [validator.py](/home/StreamForge/gateway_runtime/validator.py)
- [event_validator.py](/home/StreamForge/gateway_runtime/event_validator.py)
- [aggregator.py](/home/StreamForge/gateway_runtime/aggregator.py)
- [adapter_manager.py](/home/StreamForge/gateway_runtime/adapter_manager.py)
- [sink_manager.py](/home/StreamForge/gateway_runtime/sink_manager.py)

6. Least privilege is not truly implemented.
- The user model is still effectively admin vs non-admin.
- Non-admin users collapse into engineer-level capability.
- Fine-grained role persistence and enforcement are missing.

Primary files:
- [models.py](/home/StreamForge/control-plane/app/db/models.py)
- [security.py](/home/StreamForge/control-plane/app/core/security.py)
- [users.py](/home/StreamForge/control-plane/app/schemas/users.py)
- [UsersPage.tsx](/home/StreamForge/ui/src/features/users/UsersPage.tsx)

7. The frontend duplicates backend contract logic instead of consuming one authoritative source of truth.
- Protocol defaults, field semantics, and config shaping are hardcoded in frontend modules despite the backend catalog.

Primary files:
- [adapterForm.ts](/home/StreamForge/ui/src/features/adapters/adapterForm.ts)
- [sinkForm.ts](/home/StreamForge/ui/src/features/sinks/sinkForm.ts)
- [catalog.py](/home/StreamForge/control-plane/app/routers/catalog.py)

8. Validation still permits mixed legacy and canonical shapes instead of enforcing one clear model.

Primary file:
- [config_validation.py](/home/StreamForge/control-plane/app/core/config_validation.py)

9. Internal plumbing is still exposed too directly in operator-facing flows.
- Internal topics, DSNs, and transport details remain too central in ordinary forms.

Primary files:
- [adapterForm.ts](/home/StreamForge/ui/src/features/adapters/adapterForm.ts)
- [sinkForm.ts](/home/StreamForge/ui/src/features/sinks/sinkForm.ts)
- [catalog.py](/home/StreamForge/control-plane/app/routers/catalog.py)

### Medium

10. Weak typing is still present in production UI code.

Primary file:
- [AdaptersPage.tsx](/home/StreamForge/ui/src/features/adapters/AdaptersPage.tsx)

11. Runtime lifecycle hardening is inconsistent between equivalent startup paths.
- The adapter manager still behaves differently between bulk start and single start.

Primary file:
- [adapter_manager.py](/home/StreamForge/gateway_runtime/adapter_manager.py)

12. Broad `except Exception` handling remains too common in infrastructure code.

Primary files:
- [adapter_manager.py](/home/StreamForge/gateway_runtime/adapter_manager.py)
- [sink_manager.py](/home/StreamForge/gateway_runtime/sink_manager.py)
- [validator.py](/home/StreamForge/gateway_runtime/validator.py)
- [event_validator.py](/home/StreamForge/gateway_runtime/event_validator.py)
- [aggregator.py](/home/StreamForge/gateway_runtime/aggregator.py)

13. Some new form modules are too large and mix too many responsibilities.

Primary files:
- [adapterForm.ts](/home/StreamForge/ui/src/features/adapters/adapterForm.ts)
- [sinkForm.ts](/home/StreamForge/ui/src/features/sinks/sinkForm.ts)

14. Documentation and intent comments are still too thin in several non-trivial new modules.

Primary files:
- [adapterForm.ts](/home/StreamForge/ui/src/features/adapters/adapterForm.ts)
- [sinkForm.ts](/home/StreamForge/ui/src/features/sinks/sinkForm.ts)
- [AdaptersPage.tsx](/home/StreamForge/ui/src/features/adapters/AdaptersPage.tsx)
- [SinksPage.tsx](/home/StreamForge/ui/src/features/sinks/SinksPage.tsx)

## Remediation Backlog

### P0: Security and Control Integrity

1. Remove plaintext secret round-tripping.
- Stop returning raw secret values from adapter and sink APIs.
- Introduce masked or secret-reference-based handling.
- Remove secret echo from review panels and JSON fallbacks.

2. Remove insecure auth defaults.
- Eliminate unsafe JWT and admin-password defaults.
- Fail fast outside explicit dev-only bootstrap paths.

3. Replace browser `localStorage` token persistence.
- Move to a safer session strategy or isolate the current pattern as a documented temporary compromise.

4. Add audit fields for operational actions.
- Capture `created_by`, `updated_by`, `activated_by`, `approved_by`, and timestamps where appropriate.

5. Implement real role persistence and least privilege.
- Persist explicit roles.
- Align enforcement with those roles.

### P1: Contract and Model Discipline

6. Make the backend contract the single source of truth.
- Reduce hardcoded frontend protocol defaults and shapes.
- Consume shared backend catalog/schema metadata wherever practical.

7. Tighten validation to one canonical shape.
- Remove accidental mixed legacy/canonical tolerance unless explicitly transitional.

8. Reduce low-level transport and infrastructure plumbing in normal UX.
- Move DSNs, internal topics, and similar details behind advanced or admin-facing surfaces.

### P1: Runtime Engineering Cleanup

9. Replace all operational `print(...)` calls with structured logging.

10. Narrow broad exception handling.
- Use more explicit exception types.
- Treat broad catches as deliberate containment boundaries, not default style.

11. Fix lifecycle consistency in runtime managers.
- Make single-start and bulk-start behavior consistent.
- Ensure pruning and managed-container behavior are deterministic.

### P2: Typing, Structure, and Readability

12. Remove weak typing in the UI.
- Replace `any` and similar shortcuts with explicit domain types.

13. Split oversized form modules.
- Separate defaults, hydration, parsing, serialization, and secret-field handling.

14. Add missing documentation and intent comments.
- Focus first on modules with complex transformation or operational logic.

### P3: Verification and Enforcement

15. Add standards-aligned tests.
- Secret redaction
- auth default hard-fail behavior
- audit metadata persistence
- role enforcement
- canonical validation behavior
- runtime lifecycle and logging behavior where practical

16. Add review gates.
- stronger lint and typing enforcement
- ban operational `print(...)` usage
- detect insecure defaults

17. Re-run a formal standards audit.
- confirm what is fixed
- document what remains
- delete this file once the backlog is truly complete

## Recommended Execution Order

1. plaintext secrets
2. insecure auth defaults
3. session and token handling
4. audit trail
5. real roles and permissions
6. backend/frontend contract consolidation
7. strict validation
8. runtime logging and exception cleanup
9. lifecycle consistency
10. typing cleanup
11. module splitting
12. documentation
13. tests and enforcement
14. final audit and file removal

## Working Tracks

### Track A: Security Foundation
- items 1 to 5

### Track B: Contract Cleanup
- items 6 to 8

### Track C: Runtime Discipline
- items 9 to 11

### Track D: Code Quality Cleanup
- items 12 to 14

### Track E: Verification
- items 15 to 17
