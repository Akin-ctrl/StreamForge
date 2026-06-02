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
- The dev compose file avoids floating `latest` image tags; helper images
  without trusted semantic tags are pinned by registry digest.
- Kafka-compatible naming remains in config keys such as `KAFKA_BOOTSTRAP` and
  `kafka_bootstrap` because those describe the client protocol contract.
- Redpanda data is stored in the `redpanda-data` compose volume. The gateway
  runtime mounts that volume read-only so overflow checks observe the broker's
  storage path instead of an unrelated container filesystem.
- Production packaging, hardware sizing, image-pull templates, and remote-site
  installation guidance are still pending.

## Local Stack

The local stack is defined in `deploy/dev/docker-compose.yml`.

It starts:

- PostgreSQL for the control-plane database
- TimescaleDB for validated telemetry and aggregate sinks
- Redpanda as the local Kafka-compatible broker and schema registry endpoint
- the FastAPI control plane
- the gateway runtime
- the plant simulator plane with Modbus TCP, simulated RTU endpoints, MQTT, and
  OPC UA-style demo services
- Kafdrop and Kafka UI for stream inspection
- Prometheus
- the React UI served through Nginx

The compose project name is pinned to `deploy` so existing local container and
network names remain stable after the dev files moved under `deploy/dev/`.
This preserves the `deploy_default` Docker network expected by runtime-managed
adapter and sink containers.

## Start Fresh

Use this when you want a clean local verification run and do not need to keep
old local volumes. The seed command is a local-demo shortcut; it is not the
production-like onboarding path.

```bash
docker compose -f deploy/dev/docker-compose.yml down -v
docker compose -f deploy/dev/docker-compose.yml up -d --build
docker compose -f deploy/dev/docker-compose.yml --profile seed run --rm dev_bootstrap
```

Use this when you want to rebuild without deleting local volumes:

```bash
docker compose -f deploy/dev/docker-compose.yml up -d --build
docker compose -f deploy/dev/docker-compose.yml --profile seed run --rm dev_bootstrap
```

For production-like local verification, do not rely on `dev_bootstrap` to create
the gateway. Instead:

1. bootstrap the first admin user
2. create an enrollment token in the Gateways UI
3. start the gateway with `CONTROL_PLANE_ENROLLMENT_TOKEN`
4. approve the pending gateway in the UI
5. create adapters, sinks, validation, event, and aggregate rules
6. activate a deployment and verify dataflow

### Production-Style First Run Without Seed

Use this path when you want to verify the operator onboarding workflow without
the local-demo seed shortcut.

Start only the base services first:

```bash
docker compose -f deploy/dev/docker-compose.yml up -d --build \
  postgres timescaledb kafka plant-simulator mqtt-broker control_plane ui kafka_ui kafdrop
```

Then open the UI and bootstrap the first admin account. After login, create a
gateway enrollment token from the Gateways page.

Start or recreate the gateway runtime with the enrollment token:

```bash
CONTROL_PLANE_GATEWAY_ID=gateway-site-01 \
CONTROL_PLANE_GATEWAY_HOSTNAME=raspberrypi-line-1.local \
CONTROL_PLANE_ENROLLMENT_TOKEN='<token-from-ui>' \
CONTROL_PLANE_GATEWAY_HARDWARE_INFO='{"site":"local-verification","hardware":"raspberry-pi"}' \
docker compose -f deploy/dev/docker-compose.yml up -d --build gateway_runtime prometheus
```

The gateway should appear as pending in the Gateways page. Approve it, then
continue with adapter creation, sink creation, validation, connection testing,
deployment activation, and post-deploy observation.

Do not commit enrollment tokens or place long-lived secrets in `.env` files.
Enrollment tokens are installation-time credentials and should be copied only
into the shell/session used for the gateway start.

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

If `gateway_runtime` logs show `gateway not registered`, choose one of two paths.

For local demo data, seed the dev topology:

```bash
docker compose -f deploy/dev/docker-compose.yml --profile seed run --rm dev_bootstrap
```

For production-like testing, create an enrollment token in the UI and restart the
gateway with:

```text
CONTROL_PLANE_ENROLLMENT_TOKEN=<token>
CONTROL_PLANE_GATEWAY_ID=<stable-gateway-id>
CONTROL_PLANE_GATEWAY_HOSTNAME=<site-hostname>
```

The gateway will appear as pending until an operator approves it.

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
docker compose -f deploy/dev/docker-compose.yml up -d --build
```

## What Is Not Covered Yet

The following are intentionally outside this document until the packaging model
is finalized:

- production edge installation
- Docker image publishing and pull-template workflow
- hardware sizing
- TLS and certificate rotation procedures
- production Redpanda tuning
- Kubernetes or multi-node broker manifests
- customer-site rollback procedures

Those topics should be documented after the package/image/template workflow is
implemented, not before.
