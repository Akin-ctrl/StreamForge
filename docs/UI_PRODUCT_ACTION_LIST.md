# UI Product Action List

This list captures the remaining product-facing UI work in strict priority order so implementation stays aligned with the accepted architecture and does not drift into demo-only shortcuts.

Last updated: 2026-04-02

## Priority Order

1. `P0` End-to-end operator configuration
   - Make the UI capable of authoring a working gateway configuration without relying on `deploy/*.sample.json`.
   - Replace inferred adapter/sink discovery with a control-plane catalog.
   - Ensure the UI can create pipeline and sink records needed by the gateway runtime.

2. `P0` Built-in user management
   - Expose existing built-in user CRUD in the UI.
   - Keep first-user bootstrap separate from normal operator/user administration.
   - Add clear password confirmation and role selection for built-in users.

3. `P1` Global timestamp and locale handling
   - Add shared UI preferences for timezone selection.
   - Replace per-page ad hoc date formatting with one shared formatter.
   - Keep backend timestamps in UTC and make presentation configurable in the UI.

4. `P1` Gateway autonomy visibility
   - Show last config sync time, current config version, and recent runtime heartbeat status.
   - Surface stale/offline indicators in the operator views.

5. `P1` Health and metrics dashboard
   - Expand the Health page into an operator dashboard with gateway health state and system metrics.
   - Include CPU, memory, and network throughput where the gateway runtime can report them safely.

6. `P2` Responsive navigation and information architecture
   - Expose all supported management views in routing/navigation.
   - Reduce hidden screens and demo-only paths.

7. `P2` Richer configuration ergonomics
   - Continue improving protocol-aware forms for multi-parameter industrial sources.
   - Support broader multi-adapter and multi-sink composition as additional runtime types are implemented.

8. `P3` Logs viewer
   - Add a real log viewer only after a control-plane log transport/storage contract exists.
   - Do not fake a logs UI without backed data because that would drift from the architecture.

## Current Delivery Status

- `P0` End-to-end operator configuration: Implemented for the current catalog and sink set
- `P0` Built-in user management: Implemented for built-in auth flows
- `P1` Global timestamp and locale handling: Implemented for timezone-aware UI presentation
- `P1` Gateway autonomy visibility: Implemented in gateway and health views
- `P1` Health and metrics dashboard: Implemented against current runtime/control-plane metrics
- `P2` Responsive navigation and information architecture: Implemented for currently shipped views
- `P2` Richer configuration ergonomics: Partial
- `P3` Logs viewer: Deferred pending backend log transport/storage
