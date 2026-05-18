# StreamForge UI

React + TypeScript + Vite frontend for control-plane operator workflows.

## Implemented Views

- Login + first-user bootstrap flow
- Gateways (list, create, approve)
- Create Pipeline (guided pipeline builder)
- Health
- Alarms (list/filter, acknowledge, suppress)
- DLQ (list/filter, detail, approve/discard, bulk approve)

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

- UI baseline milestone scope is completed for Phases 1-4 tracking.
- Future UI work should follow `PROJECT_PHASES.md` active queue and ADR-011 open P2/P3 items.
