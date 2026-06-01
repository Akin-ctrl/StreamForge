# StreamForge System Architecture

**Comprehensive architecture documentation for the Industrial Data Gateway platform.**

---

## Table of Contents

1. [Core Design Principles](#core-design-principles)
2. [System Components](#system-components)
3. [Data Flow Architecture](#data-flow-architecture)
4. [Protocol Adapter System](#protocol-adapter-system)
5. [Schema Management](#schema-management)
6. [Edge Buffering Strategy](#edge-buffering-strategy)
7. [Time Semantics](#time-semantics)
8. [Configuration Distribution](#configuration-distribution)
9. [Data Quality & Validation](#data-quality--validation)
10. [Aggregation & Downsampling](#aggregation--downsampling)
11. [Alarm Lifecycle](#alarm-lifecycle)
12. [Alert Routing](#alert-routing)
13. [Security Model](#security-model)
14. [Failure Modes & Recovery](#failure-modes--recovery)
15. [State Management](#state-management)
16. [Overflow Handling](#overflow-handling)
17. [Observability](#observability)
18. [Update & Rollback Strategy](#update--rollback-strategy)
19. [Disaster Recovery](#disaster-recovery)
20. [Deployment Patterns](#deployment-patterns)
21. [Planned Copilot Tool Surface](#planned-copilot-tool-surface)

> Current status: this document describes the implemented baseline and the
> remaining production direction. StreamForge is still in production-readiness
> work. Redpanda is the chosen embedded broker direction and the local
> dev/runtime path is now Redpanda-backed, while production packaging and
> image-pull templates are still pending.

---

## Core Design Principles

### 1. Local Kafka-Compatible Stream Is the System of Record

**Non-negotiable principle**: All industrial data flows through the gateway's local Kafka-compatible stream as the authoritative local source.

**Key clarification**: 
- StreamForge manages **only the local stream broker** on each gateway
- Redpanda is the chosen embedded edge broker direction
- the local dev/runtime stack currently uses Redpanda, but production packaging is still pending
- the Kafka protocol, client libraries, topics, partitions, and consumer-group semantics remain part of the architecture
- a customer's Kafka-compatible system, if any, is treated as a **sink destination**, not as StreamForge-managed infrastructure

**Rationale**:
- **Local durability**: the gateway stream retains records during network or downstream sink outages
- **Temporal decoupling**: Adapters and sinks evolve independently
- **Replayability**: Any sink can replay from the local stream
- **Simplicity**: StreamForge is a gateway platform, not a broker operations platform

### 2. Control Plane ≠ Data Plane

**Clear separation of concerns**:

| Control Plane | Data Plane |
|---------------|------------|
| Configuration management | Protocol adapters |
| Topology visualization | Local stream broker |
| Health monitoring | Sink services |
| User interface | Data transformation |
| Planned tool/Copilot surface | Validation & aggregation |

**Benefits**:
- Control Plane failures don't stop data flow
- Gateway runs indefinitely with cached config
- Clear security boundaries

### 3. Semantic Data Classification

All data is classified at the adapter level:

| Type | Definition | Examples | Stream Topics |
|------|------------|----------|--------------|
| **Telemetry** | Continuous numeric measurements | Temperature, pressure | `telemetry.*` |
| **Events** | Discrete state changes | Valve opened, motor started | `events.*` |
| **Alarms** | Events with severity & lifecycle | Overpressure, fire detected | `alarms.*` |

**Classification is determined by adapter configuration**, not runtime detection.

### 4. Edge-First Autonomy

Gateways are fully self-contained:
- The gateway-local Kafka-compatible stream buffers all data
- Configuration cached locally
- First boot requires Control Plane
- Subsequent boots work **completely offline**
- Sinks push to customer's destinations

---

## System Components

### Control Plane Components

```
┌─────────────────────────────────────────────────────────┐
│  Control Plane                                          │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Config API   │  │     UI       │  │ Planned Tools │  │
│  │ (FastAPI)    │  │ (React/TS)   │  │  (Tools)      │  │
│  └──────┬───────┘  └──────────────┘  └───────────────┘  │
│         │                                               │
│  ┌──────┴───────┐  ┌──────────────┐                     │
│  │ PostgreSQL   │  │   Schema     │                     │
│  │ (or SQLite)  │  │   Registry   │                     │
│  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

#### 1. Config & Control API
- **Technology**: FastAPI (Python)
- **Database**: PostgreSQL (remote mode) or SQLite (local mode)
- **Endpoints**:
  - `/api/v1/gateways` - Gateway inventory, approval, status, token issue/renew, config delivery, and heartbeat surfaces (self-registration is not enabled in the currently shipped implementation)
  - `/api/v1/pipelines` - Current deployment/pipeline management path
  - `/api/v1/sinks` - Sink configuration
  - `/api/v1/schemas` - Schema management
  - `/api/v1/alarms` - Alarm management
  - `/api/v1/health` - Aggregated health metrics

#### 2. UI
- **Technology**: React + TypeScript + CSS-based design system
- **Features**:
  - Adapter, sink, and deployment management
  - Protocol-aware configuration forms
  - Gateway fleet management
  - Real-time topology visualization
  - Health dashboards
  - Alarm management with ACK/SUPPRESS
  - DLQ viewer with reprocess workflow
  - Log viewer with filtering

### Configuration Object Model

The intended operator model is:

- `Gateways` as deployment targets
- `Adapters` as first-class configured source connectors
- `Sinks` as first-class configured destination connectors
- `Deployments` as composed gateway configurations that attach adapters and sinks to a gateway, alongside validation, event, and aggregate rules

This distinction matters because the gateway runtime already supports one active gateway configuration containing multiple adapters and multiple sinks. The UI and control-plane configuration model should reflect that directly instead of implying a one-adapter-to-one-sink workflow.

#### 3. Planned Copilot Tool Surface
- **Status**: planned/deferred, not a production-complete component today
- **Intended purpose**: expose StreamForge capabilities as tools for external agents after the core runtime and operator workflows are production-trustworthy
- See [Planned Copilot Tool Surface](#planned-copilot-tool-surface) section

### Data Plane Components (Gateway)

```
┌─────────────────────────────────────────────────────────┐
│  StreamForge Gateway                                    │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │  Gateway Runtime (Python asyncio)                   ││
│  │    ├── Config Poller (30s interval)                 ││
│  │    ├── Adapter Manager                              ││
│  │    ├── Validator Module                             ││
│  │    ├── Aggregator Module                            ││
│  │    ├── Health Reporter                              ││
│  │    └── Metrics Exporter (/metrics)                  ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐  │
│  │ Local Stream  │  │ Adapters      │  │ Sinks       │  │
│  │ (Kafka API)   │  │ (Docker)      │  │ (Docker)    │  │
│  └───────────────┘  └───────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────┘
```

#### 1. Gateway Runtime
- **Technology**: Python asyncio
- **Responsibilities**:
  - Load and cache configurations
  - Manage adapter/sink containers
  - Run validator and aggregator modules (not containers)
  - Monitor component health
  - Report to Control Plane

#### 2. Protocol Adapters
- **Deployment**: Docker containers
- **Isolation**: Each adapter runs in its own container with resource limits
- **Implemented Adapters**:
  - `adapter_modbus_tcp` - Modbus TCP client
  - `adapter_modbus_rtu` - Modbus RTU over serial
  - `adapter_opcua` - OPC UA client
  - `adapter_mqtt` - MQTT subscriber

Planned or deferred adapter families include:

- `adapter_xbee` - XBee wireless
- `adapter_lora` - LoRa wireless

Adapter configuration must be protocol-aware. Flat scalar field lists are not enough for the real configuration contracts:

- Modbus adapters require repeatable point mappings, including registers and optional event/state points
- MQTT requires repeatable subscriptions and field mappings
- OPC UA requires monitored-item definitions and subscription settings

An adapter instance represents one source connection or session context and may contain many mapped signals inside it. Multi-parameter industrial sources such as PLCs, MQTT payloads, and OPC UA servers should normally be modeled as one adapter with repeatable point/subscription/monitored-item mappings, not as one adapter per parameter.

See [Adapters And Deployments Spec](ADAPTERS_AND_DEPLOYMENTS_SPEC.md) for the locked operator-facing configuration contract.

#### 3. Local Stream Broker
- **Deployment**: Embedded Kafka-compatible broker
- **Chosen direction**: Redpanda
- **Current local dev/runtime image**: `redpandadata/redpanda:v26.1.9`
- **Production packaging**: Pending
- **Storage**: Configurable (e.g., 100GB)
- **Purpose**: Buffer all data locally, survive network outages

#### 4. Sink Services
- **Deployment**: Docker containers on gateway
- **Pattern**: Kafka-compatible consumer → external writer
- **Examples**:
  - `sink_timescaledb` - Writes to TimescaleDB
  - `sink_postgres` - Writes to PostgreSQL
  - `sink_kafka` - Replicates to customer's Kafka-compatible cluster
  - `sink_s3` - Batch writes to S3 in Parquet format
  - `sink_http` - HTTP POST to cloud endpoints

#### 5. Validator Module
- **Deployment**: Module inside Gateway Runtime (not a container)
- **Purpose**: Validate data quality, route bad data to DLQ

#### 6. Aggregator Module
- **Deployment**: Module inside Gateway Runtime (not a container)
- **Purpose**: Compute multi-resolution aggregates (1s, 1min, etc.)

---

## Data Flow Architecture

### End-to-End Flow

```
          ┌─────────────────┐
          │  OT Device      │ (PLC, sensor, SCADA)
          └────────┬────────┘
                   │
                   ▼
┌───────────────────────────────────────────────┐
│  StreamForge Gateway                          │
│                                               │
│  ┌─────────────────┐                          │
│  │ Protocol Adapter│ (Docker container)       │
│  │  - Polls device │                          │
│  │  - Normalizes   │                          │
│  │  - Classifies   │                          │
│  └────────┬────────┘                          │
│           │                                   │
│           ▼                                   │
│  ┌─────────────────┐                          │
│  │  Local Stream   │ (Kafka-compatible broker)│
│  │  telemetry.raw  │                          │
│  │  events.raw     │                          │
│  │  alarms.raw     │                          │
│  └────────┬────────┘                          │
│           │                                   │
│           ├──────────────┐                    │
│           ▼              ▼                    │
│  ┌──────────────┐ ┌──────────┐                │
│  │  Validator   │ │Aggregator│                │
│  │  (module)    │ │(module)  │                │
│  └──────┬───────┘ └────┬─────┘                │
│         │              │                      │
│         ▼              ▼                      │
│  telemetry.clean  telemetry.1s                │
│  dlq.telemetry    telemetry.1min              │
└───────────────────────────────────────────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │   Sink Containers   │
         │ (S3, DB, Kafka-compatible...) │
         └─────────────────────┘
                    │
                    ▼
   ┌───────────────────────────────┐
   │  Customer's Infrastructure    │
   │  (DB, Kafka-compatible, Cloud, etc.) │
   └───────────────────────────────┘
```

### Topic Organization

**Topics by data type, partitioned by asset_id:**

```
telemetry.raw           # Raw telemetry from adapters
telemetry.clean         # Validated telemetry (GOOD/SUSPECT/UNCERTAIN)
telemetry.1s            # 1-second aggregates
telemetry.1min          # 1-minute aggregates
events.raw              # Raw events from adapters
events.clean            # Validated events
alarms.raw              # Raw alarm detections
alarms.clean            # Validated alarms with lifecycle
dlq.telemetry           # Failed telemetry validation
dlq.events              # Failed event validation
```

**Partitioning**: 12 partitions per topic, keyed by `asset_id`

---

## Protocol Adapter System

### Adapter Contract

Every adapter is a Docker container implementing this interface:

#### Input: Configuration
Passed via environment variable `ADAPTER_CONFIG` (JSON):
```json
{
  "adapter_id": "adapter_modbus_001",
  "pipeline_id": "factory_line_1",
  "protocol": "modbus_tcp",
  "source": {
    "host": "192.168.1.50",
    "port": 502,
    "unit_id": 1
  },
  "mapping": {
    "registers": {
      "40001": {"param": "temperature", "unit": "celsius", "type": "float32"}
    }
  },
  "output": {
    "kafka_bootstrap": "localhost:9092",
    "topic": "telemetry.raw",
    "asset_id": "line_1_sensor_01"
  },
  "poll_interval_ms": 1000
}
```

#### Output: Stream Messages

Adapter containers publish through the shared adapter publisher, which targets the gateway-local Kafka-compatible broker, keys records by `asset_id` when present, and waits for broker acknowledgement with `acks=all`.

```json
{
  "asset_id": "line_1_sensor_01",
  "parameter": "temperature",
  "value": 85.4,
  "unit": "celsius",
  "quality": "GOOD",
  "classification": "TELEMETRY",
  "timestamps": {
    "device_time": "2026-01-29T10:00:00.123Z",
    "gateway_time": "2026-01-29T10:00:00.456Z"
  },
  "metadata": {
    "adapter_id": "adapter_modbus_001",
    "adapter_version": "1.2.0"
  }
}
```

For Modbus adapters, contiguous or overlapping holding-register definitions are batched into shared reads before decoding so the gateway minimizes round trips to the device while preserving the same normalized message contract. Connection and read failures are handled with bounded retry/backoff and reconnect attempts inside the adapter before control falls back to container restart supervision.

#### Required Endpoints
```
GET /health  → {"status": "healthy", "last_reading_at": "..."}
GET /metrics → Prometheus format
```

---

## Schema Management

### Schema Registry Integration

- **Serialization**: Avro (mandatory)
- **Registry**: Kafka-compatible Schema Registry API. The local dev stack uses Redpanda's built-in Schema Registry endpoint.
- **Compatibility**: BACKWARD (default)

### Offline Caching

Gateways cache schemas locally for offline operation:
1. On startup, pull all relevant schemas
2. Cache to local file
3. If offline, use cached schemas
4. When online, sync updates

---

## Edge Buffering Strategy

### Embedded Kafka-Compatible Broker

Each gateway runs a single-node Kafka-compatible broker:
- **Chosen direction**: Redpanda
- **Current local dev/runtime image**: `redpandadata/redpanda:v26.1.9`
- **Production packaging**: Pending
- **Storage**: Configurable per gateway (e.g., 50-500GB)
- **Retention**: Time-based + size-based

### Why Kafka-Compatible Instead of a Custom Queue?

- Proven durability and replay
- Standard tooling and client semantics
- No custom buffering code
- Handles backpressure natively
- Redpanda keeps those semantics while reducing the operational burden for edge deployments

---

## Time Semantics

### Multi-Timestamp Approach

Every message carries multiple timestamps:

```json
{
  "timestamps": {
    "device_time": "2026-01-29T10:00:00.123Z",
    "gateway_time": "2026-01-29T10:00:00.456Z"
  },
  "clock_skew_ms": 333
}
```

| Timestamp | Purpose |
|-----------|---------|
| `device_time` | When sensor measured (authoritative for analytics) |
| `gateway_time` | When gateway received (for lag detection) |
| `clock_skew_ms` | Difference (for quality monitoring) |

**Rules**:
- Analytics use `device_time`
- If `device_time` missing → use `gateway_time`, mark quality as `UNCERTAIN`
- Alert if `clock_skew > 10 seconds`

---

## Configuration Distribution

### Pull-Based with Optional Push

```
Gateway ──(poll every 30s)──> Control Plane API
        <──(config JSON)────
```

**Optional**: WebSocket notification on config change triggers immediate pull.

### Offline Behavior

- Gateway caches control-plane config to a local file (`/data/config/gateway.json` by default)
- First boot requires Control Plane if no valid cached config exists yet
- Subsequent boots start from cached config immediately, then refresh in the background
- Gateway runs **indefinitely offline** once a valid cache has been established

---

## Data Quality & Validation

### Quality Codes

| Code | Meaning | Action |
|------|---------|--------|
| GOOD | Passed all validation | Forward to `.clean` topic |
| SUSPECT | Anomalous but valid | Forward with flag |
| UNCERTAIN | Low confidence (e.g., missing device_time) | Forward with warning |
| BAD | Failed validation | Route to DLQ |

### Validation Rules (Configurable)

- **Range checks**: Value within min/max
- **Rate-of-change**: Detect spikes
- **Duplicate detection**: Same asset + param + timestamp
- **Gap detection**: Missing expected readings

### DLQ Workflow

1. BAD messages go to `dlq.telemetry` (or `dlq.events`)
2. Operator views in UI with error reason
3. Operator can:
   - Approve single message → reprocess
   - Bulk approve → reprocess batch
   - Update validation rules → reprocess all
4. Approved messages flow to `.clean` topic

---

## Aggregation & Downsampling

### Multi-Resolution Topics

Aggregator module produces multiple resolutions:

```
telemetry.raw (100 Hz) → telemetry.1s → telemetry.1min → telemetry.1hour
```

### Aggregate Message Format

```json
{
  "asset_id": "vibration_sensor_01",
  "parameter": "vibration",
  "window_start": "2026-01-29T10:00:00Z",
  "window_end": "2026-01-29T10:01:00Z",
  "aggregates": {
    "avg": 3.42,
    "min": 2.91,
    "max": 4.15,
    "count": 6000
  }
}
```

### Configurable Per Pipeline

Each pipeline can specify which resolutions to produce.

---

## Alarm Lifecycle

### States

| State | Meaning |
|-------|---------|
| ACTIVE | Alarm condition detected |
| ACKNOWLEDGED | Operator has seen it |
| CLEARED | Condition no longer true |
| SUPPRESSED | Manually silenced |

### Responsibilities

| Action | Owner |
|--------|-------|
| Detect alarm condition | Gateway (adapter or validator) |
| ACK/SUPPRESS | Control Plane (via UI) |
| Store state | Local stream + Control Plane DB |

---

## Alert Routing

### Alert Router Sink (Optional)

Dedicated sink for routing alarms to external systems:

```yaml
routes:
  - severity: CRITICAL
    destinations: [pagerduty, sms]
  - severity: HIGH
    destinations: [slack]
  - severity: [MEDIUM, LOW]
    destinations: [email]
    digest_interval: 15min
```

### UI Visibility

All alarms visible in Control Plane UI regardless of alert routing.

---

## Security Model

### Authentication

#### Gateway Authentication
- JWT tokens (1-year validity)
- Auto-renew before expiry
- Gateway record is created in the control plane/UI before first token issuance

#### User Authentication
- Built-in username/password
- Optional OAuth2/OIDC integration

### Authorization (RBAC)

#### Roles

| Role | Permissions |
|------|-------------|
| Viewer | Read dashboards, metrics, logs |
| Operator | + ACK alarms, restart components, approve DLQ |
| Engineer | + Create/edit pipelines, modify validation rules |
| Admin | + Manage users, gateways, full access |

#### Resource Scoping

Roles can be scoped to specific gateways:
- "Engineer for Factory North only"
- "Operator for all gateways"

### Network Security

| Connection | Encryption |
|------------|------------|
| Gateway → Control Plane | TLS required |
| Sink → External | TLS required |
| Internal (localhost) | Optional (demo: none) |

---

## Failure Modes & Recovery

### Failure Handling Model

**Hybrid approach**: Simple restart + bulkhead isolation + circuit breaker

#### Component Failures

| Component | Failure | Recovery |
|-----------|---------|----------|
| Adapter | Crash | Auto-restart (max 5 in 5 min) |
| Adapter | Protocol timeout | Retry with backoff, mark DEGRADED |
| Sink | Downstream unreachable | Circuit breaker opens, local stream retains uncommitted records, retry after cooldown |
| Validator | Crash | Auto-restart, messages queue |
| Local broker | Crash | Auto-restart, data preserved |
| Gateway Runtime | Crash | Systemd restarts, children restart |

#### Bulkhead Isolation

Each adapter/sink has Docker resource limits:
- Memory limit
- CPU limit
- One failing adapter cannot starve others

#### Circuit Breaker (External Connections)

For sinks and Control Plane communication:
- **Closed**: Normal operation
- **Open**: After 5 consecutive failures, pause 30s
- **Half-open**: Try one request, success → Closed, fail → Open
- Sink consumers commit local stream offsets only after successful downstream writes so buffered records remain retryable while the breaker is open

### Recovery States

| State | Meaning |
|-------|---------|
| HEALTHY | All components working |
| DEGRADED | Some non-critical components failed |
| UNHEALTHY | Critical component failed |
| FAILED | Max retries exceeded, needs manual intervention |

---

## State Management

### State Ownership

| State | Location | Persistence |
|-------|----------|-------------|
| Gateway config | Cached locally (file) | Synced from Control Plane |
| Adapter state | In-memory | Stateless (restart clean) |
| Local stream data | Broker disk | Persistent |
| Sink progress | Kafka-compatible consumer offsets | Persistent |
| Alarm state | Local stream + Control Plane DB | Persistent |
| DLQ messages | Local stream topic | Persistent |
| Schema cache | Local file | Synced from registry |

### Key Principles

1. **The gateway-local stream is source of truth for data**
2. **Control Plane DB is source of truth for config**
3. **Stateless adapters** — restart cleanly
4. **Consumer offsets track progress** — sinks resume exactly where they left off

---

## Overflow Handling

### Tiered Overflow Strategy

When local broker storage fills up:

| Disk Usage | Action |
|------------|--------|
| 0-70% | Normal operation |
| 70-80% | Alert. Compress old segments. |
| 80-90% | Aggressive downsampling (keep 1min, discard raw older than 1hr) |
| 90-95% | Evict oldest low-priority data |
| 95%+ | Block producers. Critical alert. |

### Topic Priority

| Priority | Topics |
|----------|--------|
| Critical | `alarms.*`, `dlq.*` |
| High | `events.*`, `telemetry.1min` |
| Medium | `telemetry.1s` |
| Low | `telemetry.raw` |

Raw telemetry is evicted first. Alarms are **never** evicted.

---

## Observability

### Metrics

**Collection**: Local Prometheus + remote push

**Architecture**:
```
[Adapters /metrics]
[Sinks /metrics]
[Gateway /metrics]
       ↓
[Local Prometheus] ──(push)──> Control Plane
```

**Retention**:
- Local: 24 hours
- Control Plane: 30 days

### Logging

**Format**: Structured JSON
```json
{
  "timestamp": "2026-01-29T10:00:00Z",
  "level": "ERROR",
  "component": "adapter-modbus",
  "gateway_id": "gw-factory-01",
  "message": "Connection timeout"
}
```

**Destinations**:
- Local: 7 days, 100MB ring buffer
- Remote: Push to Control Plane (30 days)
- Optional: External (Loki, Elasticsearch)

### Health Checks

**Endpoints** (all components):
```
GET /health/live   → 200 or 503
GET /health/ready  → 200 or 503
GET /health        → Full status JSON
```

**Gateway Status Roll-up**:

| Status | Condition |
|--------|-----------|
| HEALTHY | All components healthy |
| DEGRADED | Some non-critical failed |
| UNHEALTHY | Critical component failed |
| OFFLINE | No heartbeat to Control Plane |

---

## Update & Rollback Strategy

### Version Pinning

Each gateway config specifies exact versions:
```yaml
adapters:
  modbus: "v1.2.3"
  opcua: "v2.0.1"
sinks:
  s3: "v1.0.0"
```

### Update Flow

1. Operator triggers update in UI
2. Control Plane pushes new config with version
3. Gateway pulls new container image
4. Stop old container → Start new container
5. Health check → Success: done / Fail: auto-rollback

### Rollback

- Previous image kept locally
- One-click rollback in UI
- Automatic rollback if health check fails after update

---

## Disaster Recovery

### Control Plane Backup

| What | Method | Frequency |
|------|--------|-----------|
| PostgreSQL | pg_dump | Daily + before updates |
| Schema Registry | Export | Daily |
| Config files | File backup | On change |

**Restore**: Deploy fresh → restore database → gateways reconnect.

### Gateway Recovery

**Gateways are cattle, not pets.**

| Scenario | Recovery |
|----------|----------|
| Hardware dies | Deploy new, register same ID, config pulled |
| Local broker data corrupted | Restart, affected buffered data may be lost, adapters resume polling |
| Config corrupted | Re-pull from Control Plane |

Configuration state should be recoverable from the control plane. Buffered data
that has not yet drained to a sink still depends on the gateway's local broker
disk, so disk protection and backup choices matter in production packaging.

---

## Deployment Patterns

### Control Plane Modes

| Mode | Description |
|------|-------------|
| **Remote** | Control Plane in cloud/datacenter, gateways connect |
| **Local** | Control Plane on gateway itself (single-gateway deployment) |
| **Hybrid** | Central Control Plane + local UI per gateway |

### Pattern A: Remote Control Plane

```
Cloud/Datacenter:
  └── Control Plane (API + UI + DB)

Edge (each location):
  └── Gateway (Runtime + local stream + Adapters + Sinks)
```

### Pattern B: Local (Single Gateway)

```
Gateway Device:
  ├── Control Plane (SQLite)
  ├── Gateway Runtime
  ├── Local stream broker
  ├── Adapters
  └── Sinks
```

### Pattern C: Hybrid

```
Cloud:
  └── Central Control Plane

Edge:
  ├── Gateway
  └── Local UI (optional, connects to same API)
```

---

## Planned Copilot Tool Surface

Status: planned/deferred. This section captures the intended direction, not a
production-complete subsystem in the current codebase. AI/copilot work should
remain behind the production-readiness items tracked in
[Production Readiness Reconciliation](PRODUCTION_READINESS_RECONCILIATION.md).

### Tools-First Architecture

StreamForge should expose **MCP-compatible tools**, not a monolithic agent.

**Why**: Customers may have their own orchestrating agent. Multiple agents = chaos. One agent calling multiple tools = clean.

### Architecture

```
[Customer's Orchestrating Agent]
         ↓
    [MCP Protocol]
         ↓
   ┌─────┴─────┬──────────┬──────────┐
   ↓           ↓          ↓          ↓
[StreamForge] [Data     [RAG       [ML
 Tools]       Platform]  System]   Model]
```

### Intended Tools

#### Read/Query Tools
| Tool | Purpose |
|------|---------|
| `list_gateways` | List all gateways with status |
| `get_gateway_details` | Full details for one gateway |
| `get_adapter_status` | Adapter health and metrics |
| `get_sink_status` | Sink health and lag |
| `get_logs` | Query logs with filters |
| `get_metrics` | Query metrics |
| `get_alarms` | List alarms |
| `get_dlq_messages` | Query DLQ |
| `get_config` | Read config for any component |
| `get_schemas` | List schemas |

#### Analysis Tools
| Tool | Purpose |
|------|---------|
| `diagnose_gateway` | Analyze health, suggest fixes |
| `analyze_dlq` | Pattern analysis on failed messages |
| `explain_alarm` | Context and actions for alarm |
| `compare_configs` | Diff two versions |

#### Action Tools (Require Confirmation)
| Tool | Purpose |
|------|---------|
| `suggest_config_change` | Returns diff, no apply |
| `apply_config_change` | Apply with approval token |
| `restart_component` | Restart adapter/sink |
| `approve_dlq_messages` | Reprocess DLQ messages |
| `acknowledge_alarm` | Ack an alarm |
| `generate_adapter_template` | Scaffold new adapter |
| `generate_sink_template` | Scaffold new sink |

### Built-in Copilot (Optional Future Layer)

For users who only use StreamForge:
- Chat UI in dashboard
- Uses the **same MCP tools** internally
- Can be disabled

### Safety Boundaries

#### Forbidden (Hard Blocks)
- Delete gateway
- Delete sink data
- Modify production without review
- Access credentials directly
- Execute arbitrary code
- Disable authentication
- Self-approve changes

#### Requires Confirmation
- Deploy new adapter/sink
- Change validation rules
- Update gateway version
- Modify alarm thresholds
- Restart components

#### Audit Trail
Every Copilot action logged:
```json
{
  "timestamp": "...",
  "user": "john@example.com",
  "copilot_action": "suggested_config_change",
  "target": "adapter-modbus-01",
  "approved": true,
  "approved_by": "john@example.com"
}
```

---

## Summary of Key Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Edge Buffering | Embedded Kafka-compatible broker; Redpanda chosen for edge, production packaging pending |
| 2 | Protocol Adapters | Docker containers |
| 3 | Schema Management | Avro + Schema Registry + offline caching |
| 4 | Config Distribution | Poll every 30s + optional push |
| 5 | Time Semantics | Multi-timestamp (device_time, gateway_time, clock_skew) |
| 6 | Data Quality | Validator module. GOOD/BAD/SUSPECT/UNCERTAIN. BAD → DLQ |
| 7 | Aggregation | Edge module. Multi-resolution topics |
| 8 | Serialization | Avro |
| 9 | Topics | By data type, partition by asset_id, 12 partitions |
| 10 | Alarms | ACTIVE/ACK/CLEARED/SUPPRESSED. Gateway detects, Control Plane manages |
| 11 | Classification | At adapter level via config |
| 12 | Alert Routing | Optional Alert Router sink |
| 13 | Coupling | Loosely coupled. Gateway runs offline indefinitely |
| 14 | Sinks | Docker containers on gateway |
| 15 | Autonomy | Full. First boot needs Control Plane, then offline OK |
| 16 | Registration | Operator-driven gateway records today; production enrollment/approval UX pending |
| 17 | Auth | Gateways: JWT. Users: built-in auth today; OAuth/OIDC later |
| 18 | RBAC | 4 roles + resource scoping |
| 19 | Failure | Hybrid: restart + bulkhead + circuit breaker |
| 20 | State | Local Kafka-compatible stream = data truth. Control Plane = config truth |
| 21 | Overflow | Tiered: compress → downsample → evict by priority |
| 22 | Metrics | Local Prometheus + remote push |
| 23 | Logging | Structured JSON, push to Control Plane |
| 24 | Health | Liveness/readiness/deep. Status roll-up |
| 25 | Multi-tenancy | Single-tenant (demo). Multi-tenant later if SaaS |
| 26 | Network | TLS for external. Optional for internal |
| 27 | Updates | Version pinning, operator-triggered, auto-rollback |
| 28 | DR | Control Plane backups. Gateways are cattle |
| 29 | Copilot Safety | Hard blocks, soft blocks, audit trail |
| 30 | Copilot Scope | MCP tools. Built-in Copilot optional |

---

**End of Architecture Document**

For detailed decision rationale, see [ADR documents](adr/).
