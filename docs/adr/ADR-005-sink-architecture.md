# ADR-005: Sink Architecture

**Status**: Accepted  
**Date**: 2026-01-29  
**Decision**: Deploy sinks as Docker containers on gateway

---

## Context

Data must flow from local Kafka to customer destinations:
- TimescaleDB/PostgreSQL
- Customer's Kafka cluster
- Cloud storage (S3, GCS)
- HTTP APIs
- Alerting systems (PagerDuty, Slack)

We needed to decide where sinks run and how they're deployed.

## Options Considered

### Option A: Sinks on Customer Infrastructure
- Customer deploys their own consumers
- We only provide Kafka access

**Pros**: Less for us to manage  
**Cons**: Poor UX, customer needs Kafka expertise, connectivity issues

### Option B: Sinks in Control Plane
- Centralized sinks connect to gateway Kafka
- All data flows through Control Plane

**Pros**: Centralized management  
**Cons**: Control Plane becomes data plane, latency, single point of failure

### Option C: Sinks as Docker Containers on Gateway
- Same deployment model as adapters
- Consume from local Kafka, write to external destination

**Pros**: Consistent model, gateway is self-contained, works offline (buffers)  
**Cons**: More containers on gateway, external sinks need network

### Option D: Sinks as Gateway Runtime Modules
- Built into runtime like validator
- Less overhead than containers

**Pros**: Lightweight  
**Cons**: Coupled, harder to add new sinks, version coupling

## Decision

**Option C: Docker containers on gateway** (same as adapters)

## Rationale

1. **Consistency**: Same model as adapters (container, config, health, metrics)
2. **Isolation**: Each sink isolated, one failure doesn't affect others
3. **Independence**: Add new sinks without modifying gateway
4. **Offline capable**: Sinks buffer when destination unavailable
5. **Resource limits**: Prevent one slow sink from starving others

## Sink Contract

Every sink must (same pattern as adapters):

```
Environment:
  SINK_CONFIG: JSON configuration

Endpoints:
  GET /health → {"status": "healthy", "lag": 0}
  GET /metrics → Prometheus format

Behavior:
  - Consume from specified Kafka topics
  - Write to configured destination
  - Commit offsets after successful write
  - Handle retries internally
  - Expose consumer lag in metrics
```

## Available Sinks

| Sink | Description |
|------|-------------|
| `sink-timescaledb` | Write to TimescaleDB |
| `sink-postgres` | Write to PostgreSQL |
| `sink-kafka` | Replicate to customer's Kafka |
| `sink-s3` | Batch write to S3 (Parquet) |
| `sink-http` | HTTP POST to webhook |
| `sink-alert-router` | Route alarms to PagerDuty, Slack, etc. |

## Key Clarification: Customer's Kafka

**StreamForge does not manage any "central Kafka".**

When customers need multi-gateway aggregation:
1. Each gateway has `sink-kafka` configured
2. `sink-kafka` replicates to **customer's own Kafka cluster**
3. Customer manages that cluster

This keeps StreamForge focused on the gateway, not Kafka operations.

## Consequences

### Positive
- Gateway is fully self-contained
- Consistent operational model
- Easy to add new sink types
- Bulkhead isolation

### Negative
- More containers per gateway
- Each sink needs destination connectivity

### Mitigations
- Lightweight base images
- Clear documentation per sink type
- Health checks surface connectivity issues

## Related Decisions
- [ADR-002: Protocol Adapters](ADR-002-protocol-adapters.md)
- [ADR-001: Edge Buffering](ADR-001-edge-buffering.md)
