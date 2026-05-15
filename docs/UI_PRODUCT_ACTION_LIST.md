# UI Product Action List

This list captures the remaining product-facing UI work in strict priority order so implementation stays aligned with the accepted architecture and does not drift into demo-only shortcuts.

Last updated: 2026-05-14

## Priority Order

1. `P1` Fleet operations and topology views
   - Add the broader operations views described in the architecture, especially topology visualization and cross-gateway status summaries.
   - Keep the current gateway health dashboard as the foundation rather than replacing it with a separate demo path.

2. `P1` Logs viewer
   - Add a real log viewer only after the backend log transport/storage contract exists.
   - Do not fake a logs UI without backed data because that would drift from the architecture.

3. `P1` Richer configuration ergonomics
   - Continue improving protocol-aware forms for multi-parameter industrial sources.
   - Support broader multi-adapter and multi-sink composition as additional runtime types are implemented.

4. `P1` Event and aggregate UX
   - Add operator-facing views for event-class flows and aggregated telemetry when the backend paths exist.
   - Keep the UI aligned with the architecture's `events.*`, `telemetry.1s`, and `telemetry.1min` data model.

5. `P2` Optional enterprise auth UX
   - Add OAuth/OIDC entry points and role-aware UX only after the backend auth path is implemented.
   - Keep built-in auth and first-user bootstrap as the default out-of-box experience.

## Current Delivery Status

- `P0` End-to-end operator configuration: Implemented for the current catalog and sink set
- `P0` Built-in user management: Implemented for built-in auth flows
- `P1` Global timestamp and locale handling: Implemented for timezone-aware UI presentation
- `P1` Gateway autonomy visibility: Implemented in gateway and health views
- `P1` Health and metrics dashboard: Implemented against current runtime/control-plane metrics
- `P2` Responsive navigation and information architecture: Implemented for currently shipped views
- `P1` Fleet operations and topology views: Not implemented
- `P1` Logs viewer: Deferred pending backend log transport/storage
- `P1` Richer configuration ergonomics: Partial
- `P1` Event and aggregate UX: Not implemented
- `P2` Optional enterprise auth UX: Blocked on backend auth roadmap
