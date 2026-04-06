# Control Plane API

Initial FastAPI foundation for Control Plane deliverables:

- Gateway registration and status APIs
- Pipeline CRUD APIs
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
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Fresh installs do not auto-create a built-in admin user by default. Use the login screen to create the first admin account, or call `POST /api/v1/auth/bootstrap/first-user` once while the user table is empty.

For short-lived local demos, you can opt into dev-only auto-seeding by setting:

```bash
export SF_ENVIRONMENT=dev
export SF_ALLOW_DEV_ADMIN_BOOTSTRAP=true
export SF_ADMIN_USERNAME=admin
export SF_ADMIN_PASSWORD=admin123
```

`SF_ALLOW_DEV_ADMIN_BOOTSTRAP` is rejected outside `dev`/`development`/`local`/`test` environments so weak bootstrap credentials do not leak into shared deployments.

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

From [deploy/docker-compose.dev.yml](deploy/docker-compose.dev.yml):

- `postgres` runs on `localhost:5432`
- `control_plane` runs on `localhost:8000`

The default compose stack keeps first-user bootstrap intact for the UI. If you explicitly want a fully seeded demo topology, start the optional seed helper profile:

```bash
docker compose -f deploy/docker-compose.dev.yml --profile seed up -d --build
```

Gateway poller integration env vars (set on `gateway_runtime`):

- `CONTROL_PLANE_URL=http://control_plane:8000`
- `CONTROL_PLANE_GATEWAY_ID=<gateway_id>`
- `CONTROL_PLANE_TOKEN=<gateway_jwt>`
