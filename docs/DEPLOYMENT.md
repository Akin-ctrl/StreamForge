# Local Development Deployment

This guide covers only the local development stack used to build and verify
StreamForge today.

Production packaging is intentionally not documented here yet. The long-term
direction is a packaged gateway/runtime image plus deployment templates that can
pull published images. Until that packaging exists, production-style compose,
Kubernetes, and edge-install manifests should not be treated as supported
deployment instructions.

## Current Position

- The local stream backbone is Kafka-compatible.
- Redpanda is the chosen broker direction for StreamForge.
- The current dev/runtime stack uses `redpandadata/redpanda:v26.1.9`.
- Kafka-compatible naming remains in config keys such as `KAFKA_BOOTSTRAP` and
  `kafka_bootstrap` because those describe the client protocol contract.
- Production packaging, hardware sizing, image-pull templates, and remote-site
  installation guidance are still pending.

## Local Stack

The local stack is defined in `deploy/docker-compose.dev.yml`.

It starts:

- PostgreSQL for the control-plane database
- TimescaleDB for validated telemetry and aggregate sinks
- Redpanda as the local Kafka-compatible broker and schema registry endpoint
- the FastAPI control plane
- the gateway runtime
- a Modbus simulator
- Kafdrop and Kafka UI for stream inspection
- Prometheus
- the React UI served through Nginx

## Start Fresh

Use this when you want a clean local verification run and do not need to keep
old local volumes:

```bash
docker compose -f deploy/docker-compose.dev.yml down -v
docker compose -f deploy/docker-compose.dev.yml up -d --build
docker compose -f deploy/docker-compose.dev.yml --profile seed run --rm dev_bootstrap
```

Use this when you want to rebuild without deleting local volumes:

```bash
docker compose -f deploy/docker-compose.dev.yml up -d --build
docker compose -f deploy/docker-compose.dev.yml --profile seed run --rm dev_bootstrap
```

## Local URLs

| Service | URL |
|---------|-----|
| UI | `http://localhost:5000` |
| Control plane API | `http://localhost:8001` |
| Redpanda Kafka-compatible endpoint | `localhost:9092` |
| Redpanda Schema Registry endpoint | `http://localhost:8082` |
| Kafka UI | `http://localhost:8081` |
| Kafdrop | `http://localhost:9000` |
| Prometheus | `http://localhost:9090` |
| TimescaleDB | `localhost:5434` |

Inside the Docker network, services use:

```text
KAFKA_BOOTSTRAP=kafka:9092
SCHEMA_REGISTRY_URL=http://schema_registry:8081
```

## Verify The Stack

Check container health:

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
```

Verify Redpanda is the running broker:

```bash
docker exec deploy-kafka-1 rpk version
docker exec deploy-kafka-1 rpk topic list --brokers localhost:9092
```

Verify the gateway runtime is ready:

```bash
docker exec deploy-gateway_runtime-1 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8088/health/ready', timeout=5).read().decode())"
```

Verify schema registration:

```bash
docker exec deploy-gateway_runtime-1 python -c "import urllib.request; print(urllib.request.urlopen('http://schema_registry:8081/subjects', timeout=5).read().decode())"
```

Verify TimescaleDB is receiving data:

```bash
docker exec deploy-timescaledb-1 psql -U streamforge -d streamforge -c "select 'telemetry_clean' as table_name, count(*) from telemetry_clean union all select 'telemetry_1s', count(*) from telemetry_1s union all select 'telemetry_1min', count(*) from telemetry_1min;"
```

## Test Gates

Run these before claiming the local stack is healthy:

```bash
python3 -m unittest discover -s gateway_runtime/tests
python3 -m unittest discover -s adapters/tests
python3 -m unittest discover -s sinks/tests
bash scripts/check_standards_gates.sh
git diff --check
```

If the UI was changed, also run:

```bash
cd ui
npm run build
```

If the control plane was changed, also run the control-plane test suite from
the configured development environment.

## Common Local Issues

### Gateway runtime waits for provisioning

If `gateway_runtime` logs show `gateway not registered`, seed the dev data:

```bash
docker compose -f deploy/docker-compose.dev.yml --profile seed run --rm dev_bootstrap
```

### Adapter restarts during schema registration

Redpanda's Schema Registry validates Avro defaults strictly. If an adapter
fails with `Schema Registry registration failed: HTTP 422`, inspect the Avro
schema for invalid union defaults. Fields with `default: null` must list
`"null"` first in the union.

### Old containers are still running

If managed adapter or sink containers are still on an old image after rebuild,
wait briefly for the gateway manager to reconcile them. If they do not refresh,
restart the dev stack with:

```bash
docker compose -f deploy/docker-compose.dev.yml up -d --build
```

## What Is Not Covered Yet

The following are intentionally outside this document until the packaging model
is finalized:

- production edge installation
- remote gateway enrollment runbooks
- Docker image publishing and pull-template workflow
- hardware sizing
- TLS and certificate rotation procedures
- production Redpanda tuning
- Kubernetes or multi-node broker manifests
- customer-site rollback procedures

Those topics should be documented after the package/image/template workflow is
implemented, not before.
