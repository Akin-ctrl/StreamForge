# Control Plane API

Initial FastAPI foundation for Control Plane deliverables:

- Gateway registration and status APIs
- Pipeline CRUD APIs
- PostgreSQL-backed models
- JWT authentication for gateways and users

## Run (dev)

```bash
cd control-plane
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Run (docker compose)

From [deploy/docker-compose.dev.yml](deploy/docker-compose.dev.yml):

- `postgres` runs on `localhost:5432`
- `control_plane` runs on `localhost:8000`

Gateway poller integration env vars (set on `gateway_runtime`):

- `CONTROL_PLANE_URL=http://control_plane:8000`
- `CONTROL_PLANE_GATEWAY_ID=<gateway_id>`
- `CONTROL_PLANE_TOKEN=<gateway_jwt>`
