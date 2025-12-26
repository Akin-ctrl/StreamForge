# System Architecture

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
9. [Data Quality Layer](#data-quality-layer)
10. [Aggregation & Downsampling](#aggregation--downsampling)
11. [Alert Routing](#alert-routing)
12. [Security Model](#security-model)
13. [Deployment Patterns](#deployment-patterns)

---

## Core Design Principles

### 1. Kafka is the System of Record

**Non-negotiable principle**: All industrial data must first be written to Kafka (or a Kafka-compatible log) as the authoritative source.

**Rationale**:
- **Zero data loss**: Kafka provides durable persistence independent of sink availability
- **Temporal decoupling**: Producers and consumers evolve independently
- **Replayability**: Any consumer can replay historical data
- **Backpressure handling**: Built-in flow control prevents overwhelming consumers
- **Vendor neutrality**: Kafka is open-source and cloud-agnostic

**What this eliminates**:
- Data loss when databases or cloud services fail
- Tight coupling between OT data collection and IT data consumption
- Vendor lock-in to proprietary historians or cloud platforms
- Unrecoverable pipeline failures

### 2. Control Plane ≠ Data Plane

**Clear separation of concerns**:

**Control Plane** (what should happen):
- Configuration management
- Topology visualization
- Health monitoring
- User interface
- AI Copilot

**Data Plane** (moving data reliably):
- Protocol adapters
- Kafka clusters
- Sink services
- Data transformation

**Benefits**:
- Control plane failures don't stop data flow
- Data plane scales independently
- Configuration changes don't require data plane restarts
- Clear security boundaries

### 3. Semantic Data Classification

Not all data is created equal. The system enforces classification at ingestion:

| Type | Definition | Examples | Kafka Topics |
|------|------------|----------|--------------|
| **Telemetry** | Continuous numeric measurements | Temperature, pressure, flow rate | `telemetry.*` |
| **Events** | Discrete state changes | Valve opened, motor started | `events.*` |
| **Alarms** | Events with severity & lifecycle | Overpressure, fire detected | `alarms.*` |
| **Logs** | Operational messages | Adapter crashed, config reloaded | `logs.*` |

**Why this matters**:
- Different retention policies (telemetry = 30 days, alarms = 7 years)
- Different consumers (dashboards vs compliance vs ML)
- Different schemas and query patterns
- Different quality requirements

### 4. Edge-First Design

Gateways must operate autonomously:
- Local Kafka for buffering during network outages
- Configuration cached locally
- No cloud dependency for data collection
- Automatic sync when connectivity restored

---

## System Components

### Control Plane Components

#### 1. Config & Control API
- **Technology**: FastAPI (Python)
- **Responsibilities**:
  - CRUD operations for pipelines, gateways, sinks
  - Configuration validation
  - Topology graph generation
  - Health metrics aggregation
  - Audit trail
- **Endpoints**:
  - `/api/v1/pipelines` - Pipeline management
  - `/api/v1/gateways` - Gateway registration and status
  - `/api/v1/sinks` - Sink configuration
  - `/api/v1/topology` - System topology graph
  - `/api/v1/health` - Aggregated health metrics

#### 2. Control Database
- **Technology**: PostgreSQL
- **Schema**:
  - `pipelines` - Edge and sink pipeline configurations
  - `gateways` - Registered gateway metadata
  - `adapters` - Available protocol adapters
  - `sinks` - Sink service configurations
  - `audit_log` - Immutable change history
  - `schemas` - Data schema versions

#### 3. UI
- **Technology**: React + TypeScript + TailwindCSS
- **Features**:
  - Visual pipeline builder (drag-and-drop)
  - Gateway fleet management
  - Real-time topology visualization
  - Health dashboards
  - Alarm management
  - Configuration forms

#### 4. AI Copilot
- **Technology**: Python + LangChain + OpenAI/Anthropic API
- **Capabilities**:
  - Topology analysis
  - Kafka lag detection
  - DLQ analysis
  - Configuration suggestions
  - Anomaly detection
- **Safety Rails**:
  - Read-only by default
  - Approval required for changes
  - Dry-run validation
  - Automatic rollback on metric degradation

### Data Plane Components

#### 1. Gateway Runtime
- **Technology**: Python asyncio
- **Responsibilities**:
  - Load configurations from Control API
  - Manage protocol adapter lifecycle (start/stop/restart)
  - Run local Kafka (embedded KRaft mode)
  - Monitor adapter health
  - Report metrics to Control Plane
- **Process Model**:
  ```
  gateway-runtime (main process)
    ├── Config Poller (pulls from Control API every 30s)
    ├── Adapter Manager (manages Docker containers)
    ├── Local Kafka (embedded single-node)
    ├── Health Reporter (sends metrics via Kafka)
    └── Metrics Exporter (Prometheus endpoint)
  ```

#### 2. Protocol Adapters
- **Deployment**: Docker containers
- **Standard Contract**:
  - Receives config via environment variable (JSON)
  - Publishes to Kafka topics specified in config
  - Exposes `/health` and `/metrics` endpoints
  - Logs structured JSON to stdout
- **Available Adapters**:
  - `adapter-modbus-tcp` - Modbus TCP client
  - `adapter-modbus-rtu` - Modbus RTU over serial
  - `adapter-opcua` - OPC UA client
  - `adapter-mqtt` - MQTT subscriber
  - `adapter-xbee-modbus` - XBee to virtual Modbus converter

#### 3. Kafka Clusters

**Edge Kafka** (on gateway):
- Single-node KRaft mode
- Bounded disk storage (configurable, e.g., 100GB)
- Replicates to central Kafka via MirrorMaker

**Central Kafka** (on-prem or cloud):
- Multi-broker cluster
- High availability (3+ brokers, replication factor 3)
- Long-term retention
- Schema Registry integration

**Topic Organization**:
```
telemetry.raw           # Raw telemetry from adapters
telemetry.clean         # Validated, normalized telemetry
telemetry.1s            # 1-second aggregates
telemetry.1min          # 1-minute aggregates
events.raw              # Raw events
events.clean            # Validated events
alarms.raw              # Raw alarms
alarms.clean            # Validated alarms with lifecycle
logs.adapters           # Adapter logs
logs.gateway            # Gateway runtime logs
logs.sinks              # Sink service logs
dlq.invalid_telemetry   # Failed validation
dlq.invalid_events      # Failed event validation
dlq.buffer_overflow     # Dropped due to disk limits
```

#### 4. Sink Services
- **Deployment**: Independent services (containers or VMs)
- **Pattern**: Kafka consumer → external system writer
- **Examples**:
  - `sink-timescaledb` - Writes to TimescaleDB
  - `sink-postgres` - Writes to PostgreSQL
  - `sink-cloud-api` - HTTP POST to cloud endpoints
  - `sink-s3-parquet` - Batch writes to S3 in Parquet format
  - `sink-pagerduty` - Alert routing for critical alarms

---

## Data Flow Architecture

### End-to-End Flow

```
┌─────────────────┐
│  OT Device      │ (PLC, sensor, SCADA)
│  (Modbus/OPC)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Protocol Adapter│ (containerized)
│  - Reads data   │
│  - Normalizes   │
│  - Classifies   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Edge Kafka     │ (local buffering)
│  telemetry.raw  │
│  events.raw     │
└────────┬────────┘
         │ (MirrorMaker replication)
         ▼
┌─────────────────┐
│ Central Kafka   │ (authoritative)
│  All topics     │
└────────┬────────┘
         │
         ├──────────────┬──────────────┬───────────────┐
         ▼              ▼              ▼               ▼
┌──────────────┐ ┌──────────┐ ┌──────────┐  ┌──────────────┐
│Quality       │ │Aggregator│ │Sink      │  │Alert Router  │
│Validator     │ │(Streams) │ │Services  │  │(Alarms only) │
└──────┬───────┘ └────┬─────┘ └────┬─────┘  └──────┬───────┘
       │              │            │                │
       ▼              ▼            ▼                ▼
telemetry.clean  telemetry.1s  TimescaleDB    PagerDuty
events.clean     telemetry.1min     S3         Slack
alarms.clean     telemetry.1hour    Cloud      Email
```

### Example: Offshore Oil Well

**Scenario**: Pressure sensor on offshore rig transmitting via XBee radio

**Step-by-step flow**:

1. **Physical layer**: Sensor measures 185.4 PSI, transmits via XBee
2. **XBee receiver**: Gateway hardware receives binary payload
3. **Adapter processing**:
   ```python
   # adapter-xbee-modbus container receives XBee frame
   payload = parse_xbee_frame(raw_bytes)
   # Map to virtual Modbus registers per config
   registers = {
       40001: payload.bytes[0:4],  # pressure
       40003: payload.bytes[4:8],  # temperature
   }
   # Decode and normalize
   pressure_reading = {
       "asset_id": "offshore_well_12",
       "parameter": "pressure",
       "value": 185.4,
       "unit": "psi",
       "quality": "GOOD",
       "classification": "TELEMETRY",
       "timestamps": {
           "device_time": "2025-01-10T12:01:03.123Z",
           "gateway_time": "2025-01-10T12:01:04.001Z",
           "kafka_time": None  # Set by Kafka
       }
   }
   ```

4. **Edge Kafka**: Written to `telemetry.raw` on local Kafka (acks=all)
5. **Replication**: MirrorMaker replicates to central Kafka (when network available)
6. **Quality validation**: Kafka Streams app validates:
   ```python
   if 0 < pressure < 500:  # Valid range
       quality = "GOOD"
       publish_to("telemetry.clean")
   else:
       quality = "BAD"
       publish_to("dlq.invalid_telemetry")
   ```

7. **Aggregation**: Separate Streams apps produce:
   - `telemetry.1s`: {"avg": 185.4, "min": 185.1, "max": 185.7, "count": 10}
   - `telemetry.1min`: {"avg": 185.3, "min": 184.8, "max": 186.1, "count": 600}

8. **Sinks consume**:
   - TimescaleDB sink: Writes to `telemetry_timeseries` table
   - S3 sink: Batches to Parquet files every 5 minutes
   - ML API sink: Real-time inference on `telemetry.1s`

9. **If pressure > 200 PSI**:
   - Alarm evaluator generates alarm event
   - Published to `alarms.raw`
   - Alert router reads `alarms.clean`
   - Routes CRITICAL alarms to PagerDuty

---

## Protocol Adapter System

### Adapter Contract

Every protocol adapter is a **Docker container** that implements this standard interface:

#### Input: Configuration
Passed via environment variable `CONFIG_JSON` (base64-encoded):
```json
{
  "pipeline_id": "offshore_well_12",
  "adapter_id": "adapter-xbee-modbus-001",
  "protocol": "xbee_modbus",
  "source": {
    "xbee_port": "/dev/ttyUSB0",
    "baud_rate": 9600,
    "node_id": "0013A200"
  },
  "mapping": {
    "registers": {
      "40001": {"param": "pressure", "unit": "psi", "type": "float32", "scale": 1.0},
      "40003": {"param": "temperature", "unit": "celsius", "type": "float32", "scale": 0.1}
    }
  },
  "output": {
    "kafka_bootstrap": "localhost:9092",
    "topic": "telemetry.raw",
    "classification": "TELEMETRY",
    "asset_id": "offshore_well_12",
    "schema_registry": "http://localhost:8081"
  },
  "poll_interval_ms": 1000,
  "retry_policy": {
    "max_retries": 3,
    "backoff_ms": 1000
  }
}
```

#### Output: Kafka Messages
All adapters publish messages with this structure:
```json
{
  "asset_id": "offshore_well_12",
  "parameter": "pressure",
  "value": 185.4,
  "unit": "psi",
  "quality": "GOOD",
  "classification": "TELEMETRY",
  "timestamps": {
    "device_time": "2025-01-10T12:01:03.123Z",
    "gateway_time": "2025-01-10T12:01:04.001Z",
    "kafka_time": null
  },
  "metadata": {
    "adapter_id": "adapter-xbee-modbus-001",
    "adapter_version": "1.2.0",
    "pipeline_id": "offshore_well_12",
    "hostname": "gateway-rig-alpha"
  }
}
```

#### Health Endpoint
```
GET /health
Response:
{
  "status": "healthy",  // healthy | degraded | unhealthy
  "last_reading_at": "2025-01-10T12:01:05Z",
  "readings_per_sec": 10.5,
  "errors_last_minute": 0,
  "kafka_connection": "ok"
}
```

#### Metrics Endpoint
```
GET /metrics
Response: Prometheus format
# HELP adapter_readings_total Total readings processed
# TYPE adapter_readings_total counter
adapter_readings_total{pipeline_id="offshore_well_12"} 1523

# HELP adapter_errors_total Total errors
# TYPE adapter_errors_total counter
adapter_errors_total{pipeline_id="offshore_well_12",type="connection"} 3
```

#### Lifecycle
```
1. Gateway Runtime pulls config from Control API
2. Runtime runs: docker run adapter-xbee-modbus:1.2.0 --env CONFIG_JSON=<base64>
3. Adapter starts, validates config
4. Adapter connects to Kafka
5. Adapter registers schema with Schema Registry
6. Adapter begins polling/subscribing per protocol
7. Adapter publishes to Kafka continuously
8. Gateway Runtime monitors /health every 10s
9. On config change: Runtime sends SIGTERM → graceful shutdown
10. Runtime starts new container with updated config
```

### Adapter Development

To create a new adapter:

1. **Implement the contract**:
```python
# adapter-custom/main.py
import os, json, base64
from kafka import KafkaProducer

config = json.loads(base64.b64decode(os.environ['CONFIG_JSON']))
producer = KafkaProducer(bootstrap_servers=config['output']['kafka_bootstrap'])

def read_device():
    # Protocol-specific logic
    raw_data = read_from_device(config['source'])
    
    # Normalize to standard message
    message = {
        "asset_id": config['output']['asset_id'],
        "parameter": "custom_param",
        "value": raw_data['value'],
        "quality": "GOOD",
        "timestamps": {
            "device_time": raw_data['timestamp'],
            "gateway_time": datetime.utcnow().isoformat() + "Z"
        }
    }
    
    producer.send(config['output']['topic'], value=message)
```

2. **Create Dockerfile**:
```dockerfile
FROM python:3.11-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . /app
WORKDIR /app
EXPOSE 8080
CMD ["python", "main.py"]
```

3. **Register in adapter registry**:
```bash
docker build -t adapter-custom:1.0.0 .
docker push registry.example.com/adapter-custom:1.0.0
```

4. **Control API knows about it**:
```sql
INSERT INTO adapters (name, version, image, protocol_type)
VALUES ('adapter-custom', '1.0.0', 'registry.example.com/adapter-custom:1.0.0', 'custom');
```

---

## Schema Management

### Schema Registry Integration

**Requirement**: Confluent Schema Registry or Karapace (open-source)

**Purpose**:
- Enforce data contracts
- Enable schema evolution
- Prevent incompatible changes
- Support multiple schema versions simultaneously

### Schema Evolution Strategy

**Compatibility mode**: BACKWARD (default)
- New schemas can read data written with old schemas
- Consumers upgrade independently of producers
- Safe to add optional fields
- Cannot remove required fields or change types

**Example evolution**:

**Version 1**:
```json
{
  "name": "TelemetryReading",
  "type": "record",
  "fields": [
    {"name": "asset_id", "type": "string"},
    {"name": "parameter", "type": "string"},
    {"name": "value", "type": "double"},
    {"name": "unit", "type": "string"}
  ]
}
```

**Version 2** (adding optional field):
```json
{
  "name": "TelemetryReading",
  "type": "record",
  "fields": [
    {"name": "asset_id", "type": "string"},
    {"name": "parameter", "type": "string"},
    {"name": "value", "type": "double"},
    {"name": "unit", "type": "string"},
    {"name": "quality", "type": "string", "default": "UNKNOWN"}  // NEW
  ]
}
```

### Offline Gateway Scenario

**Problem**: Gateway is offline for 3 days buffering data with schema v1. Control plane deploys schema v2. Gateway comes online.

**Solution**:
1. Gateway publishes buffered messages with schema ID header = v1
2. Gateway switches to v2 for new messages
3. Sinks read from Schema Registry and handle both versions
4. No data loss, no compatibility issues

**Kafka message headers**:
```
Headers:
  schema_id: 42  (references v1 in Schema Registry)
  
Payload:
  {... data conforming to v1 ...}
```

---

## Edge Buffering Strategy

### Architecture Decision: Embedded Kafka

**Choice**: Every gateway runs a single-node Kafka cluster (KRaft mode)

**Rationale**:
- No custom buffering code needed
- Leverages Kafka's own reliability
- Standard replication protocol (MirrorMaker)
- Built-in replay capability
- Proven at scale

### Deployment

```yaml
# docker-compose.yml on gateway
services:
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_NODE_ID: 1
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@localhost:9093'
      KAFKA_LOG_DIRS: '/var/lib/kafka/data'
      KAFKA_LOG_RETENTION_BYTES: 107374182400  # 100GB
    volumes:
      - /data/kafka:/var/lib/kafka/data
```

### Replication to Central Kafka

**MirrorMaker 2.0**:
```properties
# mm2.properties
clusters = edge, central
edge.bootstrap.servers = localhost:9092
central.bootstrap.servers = central-kafka.example.com:9093

edge->central.enabled = true
edge->central.topics = telemetry.*, events.*, alarms.*, logs.*

# Replication settings
replication.factor = 3
offset.flush.interval.ms = 10000
checkpoints.topic.replication.factor = 3
```

**Behavior**:
- When network available: Near real-time replication (lag < 1s)
- When network fails: Local Kafka buffers, MirrorMaker retries
- When network restored: Automatic catch-up (replays from last committed offset)

### Overflow Handling

**Problem**: Edge gateway disk is 100GB. Network down for 7 days. Data exceeds capacity.

**Solution**: Priority-based retention

```python
# Gateway Runtime monitors disk usage
if disk_usage > 90%:
    # Drop data in priority order (lowest first)
    priority_order = [
        'logs.*',           # Lowest priority
        'events.*',
        'telemetry.raw',
        'alarms.*'          # NEVER drop alarms
    ]
    
    for topic_pattern in priority_order:
        if disk_usage < 85%:
            break
        delete_oldest_segments(topic_pattern)
        emit_overflow_event(topic_pattern)
```

**Overflow events**:
```json
{
  "event_type": "buffer_overflow",
  "topic": "logs.adapters",
  "segments_deleted": 42,
  "bytes_freed": 5368709120,
  "oldest_timestamp": "2025-01-03T00:00:00Z",
  "newest_timestamp": "2025-01-05T12:00:00Z"
}
```

Published to: `dlq.buffer_overflow` (replicated to central when network restored)

---

## Time Semantics

### The Problem

Industrial data involves multiple timestamps:
- **Device time**: When the sensor measured it (may be inaccurate, skewed, or missing)
- **Gateway time**: When the gateway read it (accurate if gateway has NTP)
- **Kafka time**: When Kafka received it (Kafka's message timestamp)
- **Processing time**: When a consumer processes it

Which is "correct"?

### Solution: Multi-Timestamp Approach

**Every message contains all relevant timestamps**:

```json
{
  "asset_id": "reactor_temp_sensor_01",
  "parameter": "temperature",
  "value": 342.7,
  "timestamps": {
    "device_time": "2025-01-10T12:01:03.123Z",
    "gateway_time": "2025-01-10T12:01:04.001Z",
    "kafka_time": null,  // Set by Kafka broker
    "timezone": "UTC"
  },
  "clock_skew_ms": 878  // gateway_time - device_time
}
```

### Rules

1. **device_time** = authoritative for analytics and time-series queries
   - Used for charting, trend analysis, ML features
   - If missing → use gateway_time (flag quality as "UNCERTAIN")

2. **gateway_time** = used for lag detection and data quality
   - Difference from device_time indicates clock skew
   - Large skew (> 5 seconds) triggers quality alert

3. **kafka_time** = Kafka's own timestamp (automatic)
   - Used by Kafka for log retention
   - Used by consumers for exactly-once processing

4. **clock_skew** = tracked for quality monitoring
   - Alert if skew > 10 seconds (indicates NTP issues)

### Handling Clock Issues

**NTP enforcement**:
```python
# Gateway Runtime checks on startup
ntp_offset = check_ntp_sync()
if abs(ntp_offset) > 1000:  # > 1 second
    alert("Gateway clock drift detected", severity="WARNING")
    # Continue operating, but flag data quality
```

**Offline buffering**:
```python
# When gateway was offline 2025-01-10 → 2025-01-12
# Buffered message from 2025-01-10:
{
  "timestamps": {
    "device_time": "2025-01-10T08:30:00Z",      # Preserved
    "gateway_time": "2025-01-10T08:30:01Z",     # When read
    "kafka_time": "2025-01-12T14:00:00Z"        # When published (after network restored)
  }
}
```

Analytics queries use `device_time`, so late arrival doesn't affect time-series integrity.

---

## Configuration Distribution

### Pull-Based with Push Notifications

**Architecture**:
```
Control API (REST)
    ↓ (WebSocket notification on change)
Gateway Runtime
    ↓ (HTTP long-polling every 30s or on notification)
GET /api/v1/gateways/{gateway_id}/config/current
    ↓
Gateway applies config atomically
```

### Configuration Format

**Returned by Control API**:
```json
{
  "config_version": 42,
  "gateway_id": "gateway-rig-alpha",
  "updated_at": "2025-01-10T12:00:00Z",
  "pipelines": [
    {
      "pipeline_id": "offshore_well_12",
      "enabled": true,
      "adapter": {
        "type": "xbee_modbus",
        "version": "1.2.0",
        "image": "registry.example.com/adapter-xbee-modbus:1.2.0",
        "config": {
          "source": {...},
          "mapping": {...},
          "output": {...}
        },
        "resources": {
          "cpu_limit": "0.5",
          "memory_limit": "256M"
        }
      }
    }
  ],
  "kafka": {
    "bootstrap_servers": "localhost:9092",
    "replication_target": "central-kafka.example.com:9093"
  }
}
```

### Config Application Flow

```python
# Gateway Runtime pseudocode
async def apply_config(new_config):
    # 1. Validate locally
    if not validate_config(new_config):
        log_error("Config validation failed")
        report_to_control_plane(status="REJECTED")
        return
    
    # 2. Check version
    if new_config.version <= current_config.version:
        return  # Already applied or older
    
    # 3. Compute diff
    pipelines_to_start = []
    pipelines_to_stop = []
    pipelines_to_restart = []
    
    for pipeline in new_config.pipelines:
        if pipeline.id not in current_pipelines:
            pipelines_to_start.append(pipeline)
        elif pipeline.config != current_pipelines[pipeline.id].config:
            pipelines_to_restart.append(pipeline)
    
    for pipeline_id in current_pipelines:
        if pipeline_id not in new_config.pipelines:
            pipelines_to_stop.append(pipeline_id)
    
    # 4. Apply atomically
    try:
        for pid in pipelines_to_stop:
            stop_adapter(pid)
        
        for pipeline in pipelines_to_restart:
            restart_adapter(pipeline)
        
        for pipeline in pipelines_to_start:
            start_adapter(pipeline)
        
        current_config = new_config
        report_to_control_plane(status="APPLIED", version=new_config.version)
    
    except Exception as e:
        # Rollback to previous config
        apply_config(current_config)
        report_to_control_plane(status="FAILED", error=str(e))
```

### Rollback

**Explicit rollback**:
```bash
# Control API call
POST /api/v1/gateways/{gateway_id}/config/rollback
{
  "target_version": 41  # Previous known-good version
}
```

**Automatic rollback on health degradation**:
```python
# Gateway Runtime monitors adapter health after config change
async def monitor_health_after_change(pipeline_id, timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        health = check_adapter_health(pipeline_id)
        if health.status == "unhealthy":
            log_warning(f"Adapter {pipeline_id} unhealthy after config change")
            rollback_to_previous_config()
            return
        await asyncio.sleep(10)
```

### Fleet Consistency

**Intentional inconsistency** is supported for staged rollouts:

```
Gateway A: config v43 (canary)
Gateway B: config v42 (stable)
Gateway C: config v42 (stable)
```

UI shows:
```
Fleet Status:
  ✅ gateway-rig-alpha: v43 (canary)
  ✅ gateway-factory-01: v42 (stable)
  ✅ gateway-factory-02: v42 (stable)
```

Operator can:
1. Deploy v43 to gateway A
2. Monitor for 1 hour
3. If healthy → deploy v43 to all gateways
4. If unhealthy → rollback gateway A to v42

---

## Data Quality Layer

### Quality Validation Pipeline

**Architecture**:
```
Adapter → telemetry.raw → Quality Validator (Kafka Streams) → telemetry.clean
                                                             ↓
                                                        dlq.invalid_telemetry
```

### Quality Codes (IEC 61850 Compliant)

| Code | Meaning | Action |
|------|---------|--------|
| GOOD | Passed all validation | Forward to `telemetry.clean` |
| SUSPECT | Passed validation but anomalous | Forward to `telemetry.clean` with flag |
| BAD | Failed validation | Route to DLQ, do not send to sinks |
| UNCERTAIN | Sensor reported low confidence | Forward with warning |

### Validation Rules

**Range checks**:
```python
# config/validation_rules.json
{
  "parameter": "temperature",
  "unit": "celsius",
  "min": -50,
  "max": 500,
  "action_on_violation": "mark_bad"
}
```

**Rate-of-change checks**:
```python
if abs(current_value - previous_value) > threshold:
    quality = "SUSPECT"
    reason = "Abnormal rate of change"
```

**Duplicate detection**:
```python
# Same asset_id + parameter + timestamp seen twice
if (asset_id, parameter, device_time) in seen_messages:
    quality = "BAD"
    reason = "Duplicate message"
    action = "drop"
```

**Gap detection**:
```python
# Expected poll_interval = 1000ms, but 5000ms elapsed
if time_since_last_reading > 2 * poll_interval:
    emit_gap_event({
        "asset_id": asset_id,
        "expected_interval_ms": 1000,
        "actual_gap_ms": 5000,
        "missing_samples": 4
    })
```

### Implementation (Kafka Streams)

```python
# quality_validator/app.py
from kafka import KafkaConsumer, KafkaProducer

consumer = KafkaConsumer('telemetry.raw')
clean_producer = KafkaProducer()
dlq_producer = KafkaProducer()

for message in consumer:
    reading = json.loads(message.value)
    
    # Apply validation rules
    quality, reason = validate_reading(reading)
    reading['quality'] = quality
    
    if quality == "BAD":
        reading['validation_failure_reason'] = reason
        dlq_producer.send('dlq.invalid_telemetry', value=reading)
    else:
        clean_producer.send('telemetry.clean', value=reading)
```

---

## Aggregation & Downsampling

### Multi-Resolution Topics

**Problem**: 100 Hz sensor data → Kafka is expensive. Real-time dashboards don't need 100 Hz.

**Solution**: Publish multiple resolutions

```
Adapter → telemetry.raw (100 Hz)
            ↓
         Aggregator (Kafka Streams)
            ↓
         ├── telemetry.1s (1 second aggregates)
         ├── telemetry.10s (10 second aggregates)
         ├── telemetry.1min (1 minute aggregates)
         └── telemetry.1hour (1 hour aggregates)
```

### Aggregate Message Format

```json
{
  "asset_id": "vibration_sensor_01",
  "parameter": "vibration",
  "unit": "mm/s",
  "window_start": "2025-01-10T12:01:00Z",
  "window_end": "2025-01-10T12:02:00Z",
  "aggregates": {
    "avg": 3.42,
    "min": 2.91,
    "max": 4.15,
    "stddev": 0.31,
    "count": 6000,
    "p50": 3.40,
    "p95": 3.98,
    "p99": 4.10
  },
  "quality_summary": {
    "good_samples": 5998,
    "suspect_samples": 2,
    "bad_samples": 0,
    "pct_good": 99.97
  }
}
```

### Retention Policies

```
telemetry.raw → 24 hours (for debugging, replay)
telemetry.1s → 7 days (real-time dashboards)
telemetry.1min → 90 days (operational analytics)
telemetry.1hour → 2 years (compliance, reporting)
```

### Consumer Selection

```python
# Dashboard (real-time)
consumer = KafkaConsumer('telemetry.1s')

# Analytics job (historical)
consumer = KafkaConsumer('telemetry.1min')

# ML training (full resolution, specific time range)
consumer = KafkaConsumer('telemetry.raw')
consumer.seek_to_beginning()  # Replay from start
```

---

## Alert Routing

### Alarm Lifecycle

**States**:
1. **ACTIVE** - Alarm condition detected
2. **ACKNOWLEDGED** - Operator has seen it
3. **CLEARED** - Condition no longer true
4. **SUPPRESSED** - Manually silenced

**State transitions**:
```
[Condition detected] → ACTIVE
ACTIVE → [Operator acks] → ACKNOWLEDGED
ACKNOWLEDGED → [Condition clears] → CLEARED
ACTIVE → [Manual suppression] → SUPPRESSED
```

### Alarm Message Format

```json
{
  "alarm_id": "uuid-1234",
  "asset_id": "reactor_pressure",
  "type": "overpressure",
  "severity": "CRITICAL",  // CRITICAL | HIGH | MEDIUM | LOW | INFO
  "state": "ACTIVE",
  "raised_at": "2025-01-10T12:01:03Z",
  "acked_at": null,
  "acked_by": null,
  "cleared_at": null,
  "message": "Reactor pressure exceeded threshold",
  "value": 210.5,
  "threshold": 200.0,
  "unit": "psi"
}
```

### Alerting Service

**Input**: Consumes `alarms.clean`

**Output**: External notification systems

**Routing rules**:
```yaml
# alert_rules.yaml
rules:
  - condition:
      severity: CRITICAL
    actions:
      - type: pagerduty
        integration_key: ${PAGERDUTY_KEY}
      - type: sms
        phone_numbers: ["+1234567890"]
  
  - condition:
      severity: HIGH
    actions:
      - type: slack
        channel: "#alerts"
  
  - condition:
      severity: [MEDIUM, LOW]
    actions:
      - type: email
        recipients: ["ops@example.com"]
        digest_interval: 15min  # Batch into 15-min emails
```

**Deduplication**:
```python
# Don't spam same alarm repeatedly
def should_send_alert(alarm):
    key = (alarm.asset_id, alarm.type)
    
    if key in recent_alarms:
        last_sent = recent_alarms[key]
        if time.time() - last_sent < 300:  # 5 minutes
            return False  # Deduplicate
    
    recent_alarms[key] = time.time()
    return True
```

**Escalation**:
```python
# If alarm unacknowledged for 15 minutes → escalate
def check_escalation():
    for alarm in active_alarms:
        if alarm.state == "ACTIVE" and not alarm.acked_at:
            if time.time() - alarm.raised_at > 900:  # 15 min
                escalate(alarm, to="oncall_manager")
```

**Auto-acknowledge on clear**:
```python
# When alarm condition clears
def on_alarm_cleared(alarm_id):
    update_alarm(alarm_id, state="CLEARED", cleared_at=now())
    cancel_escalation(alarm_id)
```

---

## Security Model

### Authentication

**Control Plane API**:
- JWT tokens for human users
- Service accounts for machines (gateways, sinks)
- OAuth2/OIDC integration for enterprise SSO

**Kafka**:
- SASL/SCRAM for authentication
- mTLS for gateway → central Kafka replication
- Per-topic ACLs

**Gateway Registration**:
```bash
# Gateway generates certificate on first boot
openssl req -new -x509 -keyout gateway.key -out gateway.crt

# Registers with Control API (one-time)
POST /api/v1/gateways/register
{
  "gateway_id": "gateway-rig-alpha",
  "certificate": "-----BEGIN CERTIFICATE-----..."
}

# Control API returns JWT token
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2025-01-17T12:00:00Z"
}
```

### Authorization (RBAC)

**Roles**:

| Role | Permissions |
|------|-------------|
| **Operator** | View dashboards, acknowledge alarms, read logs |
| **Engineer** | Create/edit pipelines, view configs, test connections |
| **Admin** | Manage gateways, deploy configs, user management |
| **Copilot** | Read topology, suggest changes (requires approval for writes) |

**Example ACL**:
```json
{
  "user_id": "alice@example.com",
  "roles": ["Engineer"],
  "permissions": [
    "pipelines:read",
    "pipelines:create",
    "pipelines:update",
    "gateways:read",
    "dashboards:read"
  ]
}
```

### Secrets Management

**Integration**: HashiCorp Vault or AWS Secrets Manager

**Adapter credential flow**:
```python
# Adapter config references secret, not hardcoded value
{
  "source": {
    "opcua_endpoint": "opc.tcp://plc.example.com:4840",
    "username": "${secret:opcua_plc_username}",
    "password": "${secret:opcua_plc_password}"
  }
}

# Gateway Runtime resolves secrets at runtime
def resolve_secrets(config):
    for key, value in config.items():
        if isinstance(value, str) and value.startswith("${secret:"):
            secret_name = value[9:-1]  # Extract secret name
            config[key] = vault_client.get_secret(secret_name)
    return config
```

### Network Security

**Control Plane**:
- HTTPS only (TLS 1.3)
- API Gateway with rate limiting
- VPN or private network for on-prem

**Kafka**:
- TLS encryption in transit
- SASL/SCRAM authentication
- Per-topic ACLs (producers/consumers restricted)

**Gateways**:
- Outbound-only connections (no inbound except local admin)
- Firewall rules restrict to Control API + Kafka endpoints
- VPN tunnel for cloud deployments

### Audit Trail

**All configuration changes logged**:
```json
{
  "timestamp": "2025-01-10T12:00:00Z",
  "user": "alice@example.com",
  "action": "pipeline.update",
  "resource_id": "offshore_well_12",
  "changes": {
    "poll_interval_ms": {"old": 1000, "new": 500}
  },
  "ip_address": "192.168.1.100"
}
```

**Stored in**:
- Postgres `audit_log` table
- Kafka `audit_trail` topic (immutable, long retention)

---

## Deployment Patterns

### Pattern A: Edge + Cloud

**Use case**: Offshore rigs, remote factories with intermittent connectivity

**Architecture**:
```
Edge (Offshore Rig):
  - Gateway Runtime
  - Local Kafka (single-node, 100GB)
  - Protocol Adapters
  - 4G/Satellite uplink

Cloud (AWS/Azure/GCP):
  - Control Plane (API + UI + Copilot)
  - Central Kafka (3-broker cluster)
  - Sinks (TimescaleDB, S3, ML APIs)
  - Schema Registry
```

**Data flow**:
1. Adapters write to local Kafka
2. MirrorMaker replicates to cloud Kafka (when link available)
3. Cloud sinks consume from central Kafka
4. If link fails → local Kafka buffers, auto-syncs when restored

**Configuration**:
```yaml
# Edge: docker-compose.edge.yml
services:
  gateway-runtime:
    image: industrial-gateway/gateway-runtime:1.0.0
    environment:
      CONTROL_API_URL: https://api.example.com
      LOCAL_KAFKA: kafka:9092
    volumes:
      - /data:/data
  
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    volumes:
      - /data/kafka:/var/lib/kafka/data
  
  mirrormaker:
    image: confluentinc/cp-kafka:7.5.0
    command: >
      /usr/bin/connect-mirror-maker
      /etc/kafka/mm2.properties
    environment:
      EDGE_KAFKA: kafka:9092
      CENTRAL_KAFKA: ${CENTRAL_KAFKA_URL}
```

### Pattern B: Fully On-Premise

**Use case**: Air-gapped factories, regulatory restrictions

**Architecture**:
```
Data Center (On-Prem):
  - Control Plane
  - Central Kafka (3+ brokers)
  - Gateway Runtime (on industrial PCs near devices)
  - Sinks (on-prem databases)
  - No cloud connectivity
```

**Benefits**:
- Complete data sovereignty
- No internet dependency
- Low latency (all local)

**Deployment**:
```bash
# Kubernetes on-prem
kubectl apply -f deploy/k8s/onprem/
```

### Pattern C: Hybrid (Best of Both)

**Use case**: Large enterprises with edge + data center + cloud

**Architecture**:
```
Edge (Factory Floor):
  - Gateway Runtime
  - Local Kafka

On-Prem Data Center:
  - Control Plane
  - Central Kafka (primary)
  - Critical sinks (real-time databases)

Cloud:
  - Long-term storage (S3/GCS)
  - ML/analytics platforms
  - Business intelligence tools
```

**Data flow**:
1. Edge → On-prem (low latency, LAN)
2. On-prem → Cloud (batch, non-critical)
3. Alarms stay on-prem (low latency critical)

---

## AI Copilot Architecture

### Safety Model

**4-Tier Permission Model**:

**Tier 1 - Read-Only (Always Allowed)**:
- Query system topology
- Read Kafka lag metrics
- Analyze DLQs
- View configurations
- Generate insights and reports

**Tier 2 - Suggest Mode (Generates Proposals)**:
- Suggest config changes
- Propose new pipelines
- Recommend schema updates
- Draft sink configurations
- **User must approve before applying**

**Tier 3 - Supervised Execution (Requires Approval + Verification)**:
- Apply config changes
- Restart adapters
- Modify retention policies
- **Requires**: Human approval + dry-run validation + metric monitoring

**Tier 4 - Never Allowed**:
- Direct device access
- Bypass Kafka
- Delete production data
- Disable critical alarms

### Example Interaction

**User**: "Gateway latency is high on rig-alpha"

**Copilot (Tier 1 - Analysis)**:
```
Analyzing gateway rig-alpha...

Findings:
- Kafka lag: 45 seconds (normal < 5s)
- Adapter xbee-modbus-001: poll_interval = 100ms
- Reading 10,000 registers per second
- Network bandwidth: 2 Mbps

Root cause: Polling too frequently for available bandwidth.
```

**Copilot (Tier 2 - Suggestion)**:
```
Suggested fix:
- Increase poll_interval from 100ms to 500ms
- Reduce registers from 100 to 20 (high-priority only)
- Enable local aggregation (1-second rollups)

Estimated impact:
- Reduce bandwidth by 60%
- Reduce lag to < 2 seconds
- No data loss (aggregation preserves trends)

Apply this change? [Yes/No]
```

**User**: Yes

**Copilot (Tier 3 - Execution)**:
```
Applying change to pipeline xbee-modbus-001...

1. ✓ Config validated
2. ✓ Dry-run passed
3. ✓ Backup created (can rollback to v41)
4. ✓ Deploying v42
5. ⏳ Monitoring metrics (60s window)
```

**Copilot (Post-Change Monitoring)**:
```
Change successful ✓

Metrics after change:
- Kafka lag: 1.2 seconds (was 45s)
- Bandwidth: 800 Kbps (was 2 Mbps)
- Adapter health: HEALTHY
- Data quality: 100% GOOD samples

No rollback needed.
```

### Guardrails Implementation

```python
# copilot/guardrails.py
class CopilotGuardrails:
    def __init__(self):
        self.change_history = []
        self.last_change_at = None
    
    def can_apply_change(self, change):
        # Rate limit: max 1 change per 5 minutes
        if self.last_change_at:
            if time.time() - self.last_change_at < 300:
                return False, "Rate limit: wait 5 minutes between changes"
        
        # Never allow Tier 4 actions
        if change.tier == 4:
            return False, "Action not permitted for AI Copilot"
        
        # Tier 3 requires human approval
        if change.tier == 3 and not change.approved_by_human:
            return False, "Human approval required"
        
        return True, "OK"
    
    def apply_with_monitoring(self, change):
        # 1. Dry-run
        dry_run_result = validate_change(change)
        if not dry_run_result.success:
            return {"status": "failed", "reason": dry_run_result.error}
        
        # 2. Backup current config
        backup_version = create_config_backup()
        
        # 3. Apply change
        apply_change(change)
        self.last_change_at = time.time()
        
        # 4. Monitor metrics for 60 seconds
        baseline_metrics = get_current_metrics()
        time.sleep(60)
        new_metrics = get_current_metrics()
        
        # 5. Auto-rollback if degraded
        if metrics_degraded(baseline_metrics, new_metrics):
            rollback_to_config(backup_version)
            return {"status": "rolled_back", "reason": "Metrics degraded"}
        
        return {"status": "success"}
```

---

**End of Architecture Document**

For deployment details, see [DEPLOYMENT.md](DEPLOYMENT.md).
For security best practices, see [SECURITY.md](SECURITY.md).
For data flow examples, see [DATA_FLOW.md](DATA_FLOW.md).
