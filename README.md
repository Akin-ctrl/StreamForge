# StreamForge

StreamForge is an in-progress industrial data gateway for moving OT data into
modern data systems without treating the edge as an afterthought.

It is designed around a simple idea: every gateway should be able to collect
industrial signals, write them to a durable local stream backbone, keep running
through network and sink outages, and expose enough control-plane visibility for
operators and data teams to understand what is happening.

The project keeps Kafka-compatible client semantics while moving the embedded
edge broker direction to Redpanda. The local development/runtime path is now
Redpanda-backed, but production packaging and image-pull templates are still
pending.

## Why I Built This

I studied electrical and electronics engineering, and my interests sit where
industrial automation, robotics, digital twins, data engineering, and AI meet.
In industrial environments, the OT/IT gap is hard to miss: PLCs, SCADA systems,
sensors, and machines produce valuable signals, but getting those signals into
reliable, replayable, AI-ready pipelines is still harder than it should be.

StreamForge is my attempt to bridge that gap architecturally. It treats
industrial data as something that must survive bad networks, sink failures,
offline periods, changing downstream systems, and operator handoffs while still
remaining understandable to people working close to the equipment.

## Current Status

StreamForge is not a finished production product yet. It is a serious
engineering project with a working core and an honest production-readiness queue.

Implemented today:

- reusable adapter, sink, and deployment objects
- protocol-aware forms for Modbus TCP, Modbus RTU, MQTT, and OPC UA
- TimescaleDB, Kafka-compatible, HTTP, and alert-routing sink paths
- gateway runtime with local stream processing, validation, aggregation, logs,
  health, and overflow controls
- control-plane APIs for configuration, auth, RBAC, audit, alarms, DLQ, events,
  aggregates, fleet, logs, and operator checks
- React operator UI for adapters, sinks, deployments, validation/test/preflight,
  events, aggregates, fleet, logs, alarms, DLQ, health, and users
- regression coverage across control plane, runtime, adapters, sinks, and UI
  workflows

Still in progress:

- production packaging for the Redpanda-backed gateway/runtime stack
- production-grade gateway onboarding and approval flow
- gateway-executed physical-device connection tests
- topology redesign into a clearer architecture/dataflow view
- fresh-stack, failure-path, and full pre-AI verification gates
- documentation cleanup so implemented behavior and planned behavior stay
  clearly separated

## Architecture At A Glance

StreamForge is split into a control plane and a data plane.

### Control Plane

- FastAPI service for configuration, auth, RBAC, audit, gateway state, and
  operator workflows
- PostgreSQL-backed configuration and audit state
- React/TypeScript UI for operators and engineers
- Catalog-driven configuration contracts for adapters and sinks

### Data Plane

- Gateway runtime that runs at the edge
- Containerized protocol adapters for industrial sources
- Local Kafka-compatible stream backbone backed by Redpanda in the local
  dev/runtime stack
- Validator, event validator, aggregator, overflow controller, and managed sink
  processes
- Sink services that write to databases, HTTP endpoints, alert destinations, or
  customer-owned Kafka-compatible systems

The browser UI talks to the central control plane. Remote gateways call out to
the control plane for configuration and heartbeat updates. The frontend does not
need direct network access to gateways in different physical locations.

## Core Principles

### 1. The Edge Stream Is The Local Source Of Truth

Industrial data should land first in a durable local stream on the gateway.
Everything downstream should be replaceable and replayable.

Today this is implemented with Kafka-compatible clients and a Redpanda-backed
local dev/runtime stack. Production packaging is still pending, so the current
claim is local/runtime readiness rather than a finished production install
model.

### 2. Control Plane And Data Plane Stay Separate

The control plane defines what should run. The gateway runtime makes it happen
locally. If the control plane is unavailable, gateways should keep running from
their last known good configuration.

### 3. Industrial Data Needs Semantics

StreamForge separates data into:

- telemetry: continuous measurements
- events: discrete state changes
- alarms: lifecycle-aware abnormal conditions
- logs: operational/runtime messages

That model keeps downstream systems from receiving one undifferentiated stream
of industrial noise.

### 4. Operator Trust Matters

Configuration should be testable before deployment. Runtime state should be
visible without shell access. Failures should degrade clearly instead of failing
silently.

## Repository Layout

```text
streamforge/
├── control-plane/   # FastAPI control plane
├── gateway_runtime/ # Edge runtime and local orchestration
├── adapters/        # Protocol adapter implementations
├── sinks/           # Sink service implementations
├── ui/              # React/TypeScript operator UI
├── schemas/         # Avro and JSON schemas
├── deploy/          # Development deployment assets
├── docs/            # Architecture, security, readiness, and design docs
└── copilot/         # Reserved for future AI/copilot work
```

## Running Locally

The current development stack uses Redpanda as the local Kafka-compatible
broker. The config keys remain Kafka-named because they describe the protocol
contract, not a dependency on Apache Kafka or Confluent images.

```bash
docker compose -f deploy/docker-compose.dev.yml up -d --build
```

Seed the demo environment:

```bash
docker compose -f deploy/docker-compose.dev.yml --profile seed run --rm dev_bootstrap
```

The UI is exposed at:

```text
http://localhost:5000
```

Useful local checks:

```bash
cd control-plane && ./.venv/bin/python -m pytest
python3 -m unittest discover -s gateway_runtime/tests
python3 -m unittest discover -s adapters/tests
python3 -m unittest discover -s sinks/tests
cd ui && npm run build
```

## Comparison

| Area | StreamForge | SCADA/Ignition | Cloud IoT Platforms | Custom Scripts |
|------|-------------|----------------|---------------------|----------------|
| OT protocol focus | Native adapter model | Strong, often plugin-based | Limited or gateway-dependent | Manual |
| Edge autonomy | Core design goal | Varies by deployment | Often cloud-centered | Fragile |
| Local replay buffer | Built around a Kafka-compatible edge stream | Usually database/historian-centered | Cloud queue dependent | Usually absent |
| Data engineering fit | Stream-native, replayable, sink-oriented | Possible but indirect | Strong in-cloud, weaker offline | Ad hoc |
| Operator visibility | Control-plane UI and runtime health surfaces | Strong HMI/SCADA visibility | Cloud dashboards | Minimal |
| Vendor neutrality | Designed for on-prem and hybrid use | Often proprietary | Cloud lock-in risk | Depends on author |

## Roadmap

### Completed Core Scope

- architecture baseline
- control-plane API baseline
- gateway runtime baseline
- Redpanda-backed local dev/runtime broker path
- reusable adapters, sinks, and deployments
- validation, test connection, and deployment preflight flows
- events, aggregates, fleet, logs, alarms, and DLQ operator views
- RBAC, audit trail, safer browser sessions, and secret-field handling

### Active Production-Readiness Work

- finish production packaging and image-pull templates for the Redpanda-backed
  gateway/runtime stack
- implement production-grade gateway enrollment and approval
- add gateway-side physical-device verification
- improve topology into a true dataflow/architecture view
- finish responsive/readability hardening
- complete fresh-stack and failure-path verification before AI work continues

### Later

- additional industrial adapters and sink destinations
- deeper production observability and long-term log retention
- optional enterprise auth UX
- AI/copilot features after the core platform is trustworthy enough to support
  them

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Data Flow](docs/DATA_FLOW.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Security](docs/SECURITY.md)
- [Production Readiness Reconciliation](docs/PRODUCTION_READINESS_RECONCILIATION.md)
- [UI Product Action List](docs/UI_PRODUCT_ACTION_LIST.md)
- [Adapter Development](adapters/README.md)
- [Control Plane API](control-plane/README.md)

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).

## Contributing

This project is currently owner-led while the core architecture and production
readiness work settle. Technical feedback, issue reports, and review comments
are welcome, especially around industrial protocols, edge reliability, and
operator workflow quality.

## Support

There is no commercial support channel yet. For now, use GitHub issues or my public contact channels for questions and feedback.
