# Control Plane API

Initial FastAPI foundation for Control Plane deliverables:

- Gateway registration and status APIs
- Adapter, sink, and deployment CRUD APIs
- Alarm ingest and lifecycle APIs
- DLQ ingest, review, and reprocess/discard APIs
- PostgreSQL-backed models
- JWT authentication for gateways and users
- First-user bootstrap flow for the initial built-in admin account

## Run (dev)

```bash
cd control-plane
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SF_JWT_SECRET='LocalJwtSecretKey9482LocalJwtSecretKey9482'
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Fresh installs do not auto-create a built-in admin user by default. Use the login screen to create the first admin account, or call `POST /api/v1/auth/bootstrap/first-user` once while the user table is empty.
Browser logins and first-user bootstrap now also establish an `HttpOnly` session cookie for the UI, while the JSON token response remains available for scripts and non-browser clients.

For short-lived local demos, you can opt into dev-only auto-seeding by setting:

```bash
export SF_ENVIRONMENT=dev
export SF_JWT_SECRET='LocalJwtSecretKey9482LocalJwtSecretKey9482'
export SF_ALLOW_DEV_ADMIN_BOOTSTRAP=true
export SF_ADMIN_USERNAME=streamforge_admin
export SF_ADMIN_PASSWORD=LocalAdminBootstrap42
```

`SF_JWT_SECRET` must always be set explicitly and must be a strong value. `SF_ALLOW_DEV_ADMIN_BOOTSTRAP` is rejected outside `dev`/`development`/`local`/`test` environments, and the bootstrap username/password must also be provided explicitly with a strong password.

## Migrations

Schema changes are managed through Alembic. The API no longer creates tables on startup.

```bash
cd control-plane
source .venv/bin/activate
alembic upgrade head
```

To author a new migration after model changes:

```bash
alembic revision --autogenerate -m "describe change"
```

The container entrypoint runs `alembic upgrade head` before starting `uvicorn`, so Docker-based dev boot stays seamless while production can still run migrations as an explicit deployment step.

## Run (docker compose)

From [deploy/dev/docker-compose.yml](../deploy/dev/docker-compose.yml):

- `postgres` runs on `localhost:5432`
- `control_plane` runs on `localhost:8001`

The default compose stack keeps first-user bootstrap intact for the UI. If you explicitly want a fully seeded demo topology, start the optional seed helper profile:

```bash
docker compose -f deploy/dev/docker-compose.yml --profile seed up -d --build
```

The optional seed profile uses explicit dev-only admin credentials from the compose file and follows the first-user bootstrap flow when the control plane has no users yet.

Gateway poller integration env vars (set on `gateway_runtime`):

- `CONTROL_PLANE_URL=http://control_plane:8000`
- `CONTROL_PLANE_GATEWAY_ID=<gateway_id>`
- `CONTROL_PLANE_TOKEN=<gateway_jwt>`
