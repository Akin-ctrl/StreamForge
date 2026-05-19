# StreamForge UI

React + TypeScript + Vite frontend for control-plane operator workflows.

## Implemented Views

- Login + first-user bootstrap flow
- Overview
- Fleet
- Gateways (list, create, approve)
- Adapters
- Deployments / Compose Deployment
- Sinks
- Events
- Aggregates
- Logs
- Health
- Alarms (list/filter, acknowledge, suppress)
- DLQ (list/filter, detail, approve/discard, bulk approve)
- Users

## Run Locally

```bash
cd ui
npm install
npm run dev
```

By default, API requests use same-origin (`/api/...`) so local production-like runs should use the nginx reverse proxy setup.
The browser UI now relies on an `HttpOnly` auth session cookie rather than storing bearer tokens in `localStorage`, so same-origin deployment remains the recommended path.

## Build

```bash
npm run build
```

## Environment

- `VITE_CONTROL_PLANE_URL` (optional)
   - If unset, UI uses same-origin API calls.
   - Set explicitly only for cross-origin local dev cases.

## Status Notes

- The current operator UI covers the core reusable-object workflow: adapters, sinks, deployments, validation/test/preflight, events, aggregates, fleet, and logs.
- The next active UI roadmap item is general configuration UX polish.
- Broader roadmap tracking now lives in `docs/UI_PRODUCT_ACTION_LIST.md` and `PROJECT_PHASES.md`.
