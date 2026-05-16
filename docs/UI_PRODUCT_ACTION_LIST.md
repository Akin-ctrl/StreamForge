# UI Product Action List

This list captures the remaining product-facing UI work in strict priority order so implementation stays aligned with the accepted architecture and does not drift into demo-only shortcuts.

Last updated: 2026-05-16

## Priority Order

1. `P0` Correct the UI information architecture
   - Reframe the current `pipeline` UX around the actual runtime model: one active gateway deployment/config at a time, with multiple adapters and multiple sinks inside it.
   - Stop implying that a pipeline is only one adapter to one sink.
   - Decide whether to keep the word `pipeline` in the UI or rename the composition surface to something closer to `deployment`, `gateway config`, or `dataflow`.
   - Align the main information architecture around `Gateways`, `Adapters`, `Sinks`, and `Pipelines/Deployments`.

2. `P0` Add a first-class Adapters section
   - Create an adapter inventory/management page similar to sinks.
   - Let operators configure adapters independently before composing them into a gateway deployment.
   - Add lifecycle/status visibility for configured adapters.

3. `P0` Rework the pipeline builder into a composition/deployment builder
   - Make the builder select from configured adapters and configured sinks instead of forcing everything through one mixed wizard.
   - Support multiple adapters in one deployment.
   - Support multiple sinks in one deployment.
   - Keep validation, event, and aggregate controls visible at the deployment level where appropriate.

4. `P0` Make adapter and sink configuration fully catalog-driven
   - Remove lingering hardcoded frontend assumptions where possible.
   - Drive available adapter and sink types from the control-plane catalog rather than UI-local lists.
   - Extend catalog metadata as needed with help text, grouping, defaults, repeatable sections, and richer field hints.

5. `P1` Add protocol-aware configuration UX
   - Add dedicated authoring for Modbus RTU serial settings, MQTT subscriptions/field mappings, and OPC UA monitored items.
   - Continue improving multi-parameter industrial-source configuration ergonomics.
   - Avoid forcing operators to think in generic `config_values` terms.

6. `P1` Clarify object ownership and reuse in the UI
   - Make it clear whether adapters and sinks are reusable configured objects or deployment-local definitions.
   - Reflect the real backend/runtime ownership model honestly while keeping the operator UX clean.

7. `P1` Add connection test and preflight UX
   - Add adapter and sink config test flows where practical.
   - Surface deployment readiness and validation errors before apply/save.

8. `P1` Event and aggregate UX
   - Add operator-facing views for `events.*`, `telemetry.1s`, and `telemetry.1min`.
   - Add event and aggregate summaries to the broader operations experience.

9. `P1` Fleet operations and topology views
   - Add the broader operations views described in the architecture, especially topology visualization and cross-gateway status summaries.
   - Keep the current gateway health dashboard as the foundation rather than replacing it with a separate demo path.

10. `P1` Logs viewer
   - Add a real log viewer only after the backend log transport/storage contract exists.
   - Do not fake a logs UI without backed data because that would drift from the architecture.

11. `P1` General configuration UX polish
   - Improve summaries, empty states, loading/error handling, and sink-specific form ergonomics.
   - Reduce the current table-and-raw-form feel for complex operator workflows.

12. `P2` Design-system consistency and reusable UI primitives
   - Strengthen reusable components for forms, cards, badges, detail panes, and status surfaces.
   - Keep this behind the higher-priority information-architecture and configuration-model work.

13. `P2` Optional enterprise auth UX
   - Add OAuth/OIDC entry points and role-aware UX only after the backend auth path is implemented.
   - Keep built-in auth and first-user bootstrap as the default out-of-box experience.

## Current Delivery Status

- `P0` End-to-end operator configuration: Implemented only for the current narrow wizard model; needs architecture correction for multi-adapter/multi-sink deployment composition
- `P0` Built-in user management: Implemented for built-in auth flows
- `P1` Global timestamp and locale handling: Implemented for timezone-aware UI presentation
- `P1` Gateway autonomy visibility: Implemented in gateway and health views
- `P1` Health and metrics dashboard: Implemented against current runtime/control-plane metrics
- `P2` Responsive navigation and information architecture: Implemented for currently shipped views
- `P0` UI information architecture correction: Not implemented
- `P0` Adapters section: Not implemented
- `P0` Deployment/composition builder rework: Not implemented
- `P0` Catalog-driven adapter/sink rendering: Partial
- `P1` Protocol-aware configuration UX: Partial
- `P1` Object ownership/reuse clarity: Not implemented
- `P1` Connection test and preflight UX: Not implemented
- `P1` Event and aggregate UX: Not implemented
- `P1` Fleet operations and topology views: Not implemented
- `P1` Logs viewer: Deferred pending backend log transport/storage
- `P1` General configuration UX polish: Partial
- `P2` Design-system consistency: Partial
- `P2` Optional enterprise auth UX: Blocked on backend auth roadmap
