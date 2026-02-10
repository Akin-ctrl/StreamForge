# Data Flow Documentation

**Detailed data flow examples across different industrial scenarios.**

---

## Table of Contents

1. [Core Data Flow Pattern](#core-data-flow-pattern)
2. [Example 1: Offshore Oil Well (XBee → Kafka → Cloud)](#example-1-offshore-oil-well-xbee--kafka--cloud)
3. [Example 2: Smart Factory (Modbus PLC → TimescaleDB)](#example-2-smart-factory-modbus-plc--timescaledb)
4. [Example 3: OPC UA → Real-time Dashboard](#example-3-opc-ua--real-time-dashboard)
5. [Example 4: Network Outage Recovery](#example-4-network-outage-recovery)
6. [Example 5: Alarm Lifecycle](#example-5-alarm-lifecycle)
7. [Message Format Examples](#message-format-examples)

---

## Core Data Flow Pattern

**Every data flow follows this pattern**:

```
Physical Device
    ↓ (Protocol: Modbus/OPC UA/MQTT/XBee/etc.)
Protocol Adapter (Container)
    ↓ (Normalized message)
Edge Kafka (Local buffering)
    ↓ (MirrorMaker replication)
Central Kafka (System of record)
    ↓ (Multi-path consumption)
    ├─→ Quality Validator → telemetry.clean
    ├─→ Aggregator → telemetry.1s, telemetry.1min
    ├─→ Sink Services → Databases, Cloud, APIs
    └─→ Alert Router → PagerDuty, Slack, Email
```

---

## Example 1: Offshore Oil Well (XBee → Kafka → Cloud)

### Scenario
- **Location**: Offshore oil rig, 50km from shore
- **Connectivity**: Intermittent 4G/satellite (down 30% of the time)
- **Device**: Pressure sensor transmitting via XBee radio
- **Requirements**: Zero data loss, critical alarm routing

### Configuration

**Step 1: UI Configuration**

User creates pipeline via UI:
```
Pipeline Name: offshore_well_12
Protocol: XBee → Modbus Virtual
Device: XBee Node ID 0013A200
Parameters:
  - Register 40001: Pressure (PSI)
  - Register 40003: Temperature (Celsius)
Classification: Telemetry
Destination: telemetry.raw
Poll Interval: 1000ms
```

**Step 2: Generated Config (sent to Gateway)**

```json
{
  "pipeline_id": "offshore_well_12",
  "adapter": {
    "type": "xbee_modbus",
    "version": "1.2.0",
    "image": "registry.example.com/adapter_xbee_modbus:1.2.0",
    "config": {
      "source": {
        "xbee_port": "/dev/ttyUSB0",
        "baud_rate": 9600,
        "node_id": "0013A200"
      },
      "mapping": {
        "registers": {
          "40001": {
            "param": "pressure",
            "unit": "psi",
            "type": "float32",
            "scale": 1.0
          },
          "40003": {
            "param": "temperature",
            "unit": "celsius",
            "type": "float32",
            "scale": 0.1
          }
        }
      },
      "output": {
        "kafka_bootstrap": "localhost:9092",
        "topic": "telemetry.raw",
        "classification": "TELEMETRY",
        "asset_id": "offshore_well_12"
      },
      "poll_interval_ms": 1000
    }
  }
}
```

### Data Flow (Normal Operation)

**Time: 12:01:03.123 - Physical measurement**
```
Sensor: Pressure = 185.4 PSI, Temperature = 34.2°C
XBee transmits: [Binary frame with 8 bytes payload]
```

**Time: 12:01:03.987 - XBee reception**
```
Gateway XBee receiver: Receives frame
Adapter container: Decodes payload
  Bytes 0-3 → 185.4 (float32)
  Bytes 4-7 → 342 (int16, scale 0.1) = 34.2°C
```

**Time: 12:01:04.001 - Normalization**
```python
# Adapter code
reading = {
    "asset_id": "offshore_well_12",
    "parameter": "pressure",
    "value": 185.4,
    "unit": "psi",
    "quality": "GOOD",
    "classification": "TELEMETRY",
    "timestamps": {
        "device_time": "2025-01-10T12:01:03.123Z",  # From XBee frame
        "gateway_time": "2025-01-10T12:01:04.001Z",  # Gateway clock
        "kafka_time": None  # Set by Kafka
    },
    "metadata": {
        "adapter_id": "adapter_xbee_modbus_001",
        "adapter_version": "1.2.0",
        "pipeline_id": "offshore_well_12"
    }
}
```

**Time: 12:01:04.015 - Edge Kafka write**
```
Topic: telemetry.raw
Partition: 0 (keyed by asset_id)
Offset: 1523847
Message: [JSON above]
Acks: all (written to disk before acknowledge)
```

**Time: 12:01:04.050 - MirrorMaker replication**
```
Source: Edge Kafka (localhost:9092)
Target: Central Kafka (central.example.com:9093)
Lag: ~35ms
Status: ✓ Replicated
```

**Time: 12:01:04.100 - Central Kafka**
```
Topic: telemetry.raw
Partition: 12
Offset: 9834521
Replication factor: 3 (3 brokers)
```

**Time: 12:01:04.200 - Quality Validation**
```python
# Kafka Streams app
input: telemetry.raw
validation:
  ✓ 0 < pressure < 500 PSI
  ✓ -50 < temperature < 200 °C
  ✓ timestamps valid
  ✓ no duplicates
quality: GOOD
output: telemetry.clean
```

**Time: 12:01:05.000 - Aggregation**
```python
# 1-second window aggregator
window: [12:01:04.000 → 12:01:05.000]
samples: 1 (only this reading in this second)
output to telemetry.1s:
{
  "asset_id": "offshore_well_12",
  "parameter": "pressure",
  "window_start": "2025-01-10T12:01:04Z",
  "window_end": "2025-01-10T12:01:05Z",
  "avg": 185.4,
  "min": 185.4,
  "max": 185.4,
  "count": 1
}
```

**Time: 12:01:04.300 - Sink writes**
```
Sink: TimescaleDB
Table: telemetry_timeseries
SQL: INSERT INTO telemetry_timeseries (time, asset_id, parameter, value, unit, quality)
     VALUES ('2025-01-10T12:01:03.123Z', 'offshore_well_12', 'pressure', 185.4, 'psi', 'GOOD')

Sink: S3 Parquet (batched every 5 min)
Buffer: In-memory, will flush at 12:05:00

Sink: Cloud ML API
HTTP POST to https://ml.example.com/predict
Body: {"timestamp": "...", "pressure": 185.4, "temperature": 34.2}
```

### Data Flow (Network Outage)

**Time: 14:30:00 - Network fails**
```
4G link down
MirrorMaker: Connection failed, retrying...
Edge Kafka: Continues accepting writes (local disk)
```

**Time: 14:30:01 → 17:00:00 - 2.5 hours offline**
```
Adapter: Still reading sensor every 1s
Edge Kafka: Buffering locally
  Topics: telemetry.raw, events.raw
  Disk usage: 42% → 58% (16GB accumulated)
  Status: ✓ No data loss
```

**Time: 17:00:00 - Network restored**
```
MirrorMaker: Connection re-established
Replication lag: 2.5 hours (9,000 messages)
Catch-up speed: ~1000 msg/sec
```

**Time: 17:02:30 - Fully synced**
```
All buffered data replicated to central Kafka
Central sinks catch up:
  - TimescaleDB: Writes 9,000 rows (backfill)
  - S3: Creates Parquet files for offline period
  - ML API: Skips (real-time only)
```

**Result**: Zero data loss, historical analysis intact

---

## Example 2: Smart Factory (Modbus PLC → TimescaleDB)

### Scenario
- **Location**: Factory floor, stable LAN
- **Device**: Modbus TCP PLC (assembly line controller)
- **Requirements**: Real-time dashboard, historical analytics

### Configuration

```json
{
  "pipeline_id": "assembly_line_plc_01",
  "adapter": {
    "type": "modbus_tcp",
    "version": "1.0.5",
    "config": {
      "source": {
        "host": "192.168.10.50",
        "port": 502,
        "unit_id": 1
      },
      "mapping": {
        "holding_registers": {
          "40001": {"param": "conveyor_speed", "unit": "m/min", "type": "uint16"},
          "40002": {"param": "motor_current", "unit": "amps", "type": "uint16", "scale": 0.1},
          "40003": {"param": "cycle_count", "unit": "count", "type": "uint32"}
        },
        "coils": {
          "00001": {"param": "motor_running", "type": "bool"}
        }
      },
      "output": {
        "kafka_bootstrap": "kafka.factory.local:9092",
        "telemetry_topic": "telemetry.raw",
        "events_topic": "events.raw",
        "asset_id": "assembly_line_plc_01"
      },
      "poll_interval_ms": 500
    }
  }
}
```

### Data Flow

**Every 500ms**:

```
Modbus TCP request to 192.168.10.50:502
Read holding registers 40001-40003
Read coil 00001

Response:
  40001 = 120 → conveyor_speed = 120 m/min
  40002 = 153 → motor_current = 15.3 amps
  40003 = 48291 → cycle_count = 48291
  00001 = 1 → motor_running = true
```

**Adapter publishes 3 messages**:

**Message 1 (Telemetry)**:
```json
{
  "asset_id": "assembly_line_plc_01",
  "parameter": "conveyor_speed",
  "value": 120,
  "unit": "m/min",
  "classification": "TELEMETRY",
  "timestamps": {...}
}
```

**Message 2 (Telemetry)**:
```json
{
  "asset_id": "assembly_line_plc_01",
  "parameter": "motor_current",
  "value": 15.3,
  "unit": "amps",
  "classification": "TELEMETRY",
  "timestamps": {...}
}
```

**Message 3 (Event - only when state changes)**:
```json
{
  "asset_id": "assembly_line_plc_01",
  "event_type": "motor_state_change",
  "previous_state": false,
  "new_state": true,
  "classification": "EVENT",
  "timestamps": {...}
}
```

**Kafka → TimescaleDB**:
```sql
-- Sink writes to hypertable
INSERT INTO telemetry_timeseries (time, asset_id, parameter, value, unit)
VALUES 
  ('2025-01-10T08:30:00.123Z', 'assembly_line_plc_01', 'conveyor_speed', 120, 'm/min'),
  ('2025-01-10T08:30:00.123Z', 'assembly_line_plc_01', 'motor_current', 15.3, 'amps');

INSERT INTO events (time, asset_id, event_type, previous_state, new_state)
VALUES ('2025-01-10T08:30:00.123Z', 'assembly_line_plc_01', 'motor_state_change', false, true);
```

**Dashboard queries**:
```sql
-- Real-time (last 60 seconds)
SELECT time, value 
FROM telemetry_timeseries 
WHERE asset_id = 'assembly_line_plc_01' 
  AND parameter = 'conveyor_speed'
  AND time > NOW() - INTERVAL '60 seconds'
ORDER BY time DESC;

-- Historical (last 24 hours, 1-minute averages)
SELECT time_bucket('1 minute', time) AS bucket,
       AVG(value) as avg_speed
FROM telemetry_timeseries
WHERE asset_id = 'assembly_line_plc_01'
  AND parameter = 'conveyor_speed'
  AND time > NOW() - INTERVAL '24 hours'
GROUP BY bucket
ORDER BY bucket;
```

---

## Example 3: OPC UA → Real-time Dashboard

### Scenario
- **Device**: OPC UA server (SCADA system)
- **Pattern**: Subscription-based (push, not poll)

### Configuration

```json
{
  "pipeline_id": "scada_opcua_reactor",
  "adapter": {
    "type": "opcua",
    "version": "2.1.3",
    "config": {
      "source": {
        "endpoint": "opc.tcp://scada.example.com:4840",
        "security_mode": "SignAndEncrypt",
        "security_policy": "Basic256Sha256",
        "username": "${secret:opcua_username}",
        "password": "${secret:opcua_password}"
      },
      "subscriptions": [
        {
          "node_id": "ns=2;s=Reactor.Temperature",
          "param": "reactor_temperature",
          "unit": "celsius",
          "sampling_interval_ms": 100
        },
        {
          "node_id": "ns=2;s=Reactor.Pressure",
          "param": "reactor_pressure",
          "unit": "bar",
          "sampling_interval_ms": 100
        }
      ],
      "output": {
        "kafka_bootstrap": "localhost:9092",
        "topic": "telemetry.raw",
        "asset_id": "reactor_01"
      }
    }
  }
}
```

### Data Flow

**Subscription-based (push from OPC UA server)**:

```
OPC UA Server: Value changed (reactor_temperature = 342.7°C)
  ↓ (push notification)
Adapter: Receives data change notification
  ↓
Publishes to Kafka immediately (no polling delay)
```

**High-frequency data (100ms sampling)**:
```
10:00:00.000 → temp=342.5
10:00:00.100 → temp=342.6
10:00:00.200 → temp=342.7
10:00:00.300 → temp=342.8
...
(10 readings/second)
```

**Aggregation saves bandwidth**:
```
telemetry.raw: 10 msg/sec per parameter = 20 msg/sec total
telemetry.1s: 2 msg/sec (aggregated)
telemetry.1min: 0.033 msg/sec (aggregated)

Dashboard consumes telemetry.1s (sufficient resolution)
```

---

## Example 4: Network Outage Recovery

### Timeline

**Day 1, 10:00 - Normal operation**
```
Edge gateway online
Replication lag: 50ms
Disk usage: 20GB / 100GB
```

**Day 1, 14:30 - Network failure**
```
Satellite link down (storm)
MirrorMaker: Retrying connection...
Edge Kafka: Buffering locally
Adapters: Continue operating normally
```

**Day 1, 14:30 → Day 3, 08:00 (41.5 hours offline)**
```
Total messages buffered: 149,400 (1 msg/sec × 41.5 hours)
Disk usage: 20GB → 52GB (+32GB)
Topics buffered:
  - telemetry.raw: 120,000 messages
  - events.raw: 28,000 messages
  - alarms.raw: 1,200 messages
  - logs.*: 200 messages
```

**Day 3, 08:00 - Network restored**
```
MirrorMaker: Connection re-established
Replication begins:
  Offset lag: 149,400 messages
  Throughput: 2,000 msg/sec
  ETA: ~75 seconds to catch up
```

**Day 3, 08:01:15 - Fully synced**
```
All data replicated to central Kafka
Central sinks processing backlog:
  - TimescaleDB: Bulk insert 120,000 rows (30 seconds)
  - S3 Parquet: Creates files for 41.5-hour gap (10 seconds)
  - Alerting: Processes 1,200 alarms (checks if still active)
```

**Result**:
- ✓ Zero data loss
- ✓ Historical continuity maintained
- ✓ Alarms processed in order
- ✓ Automatic recovery, no operator intervention

---

## Example 5: Alarm Lifecycle

### Scenario: Overpressure Alarm

**Time: 15:30:00 - Threshold crossed**
```
Sensor reading: pressure = 205 PSI (threshold = 200 PSI)

Adapter evaluates alarm condition (configured in pipeline):
{
  "alarm_rules": [
    {
      "parameter": "pressure",
      "condition": "value > 200",
      "severity": "CRITICAL",
      "type": "overpressure"
    }
  ]
}

Publishes alarm to alarms.raw:
{
  "alarm_id": "alarm-uuid-1234",
  "asset_id": "offshore_well_12",
  "type": "overpressure",
  "severity": "CRITICAL",
  "state": "ACTIVE",
  "raised_at": "2025-01-10T15:30:00.123Z",
  "value": 205,
  "threshold": 200,
  "unit": "psi",
  "message": "Pressure exceeded critical threshold"
}
```

**Time: 15:30:00.500 - Alert routing**
```
Alerting Service consumes alarms.raw
Severity: CRITICAL
Routing rule match:
  → PagerDuty incident created
  → SMS sent to on-call engineer
  → Slack message to #critical-alarms
```

**Time: 15:32:00 - Operator acknowledges**
```
Operator Alice clicks "Acknowledge" in UI

UI sends:
POST /api/v1/alarms/alarm-uuid-1234/acknowledge
{
  "acked_by": "alice@example.com"
}

Control API publishes to alarms.raw:
{
  "alarm_id": "alarm-uuid-1234",
  "state": "ACKNOWLEDGED",
  "acked_at": "2025-01-10T15:32:00Z",
  "acked_by": "alice@example.com"
}

Alerting Service:
  - Cancels escalation timer
  - Updates PagerDuty incident status
```

**Time: 15:45:00 - Pressure returns to normal**
```
Sensor reading: pressure = 198 PSI (below threshold)

Adapter evaluates: condition no longer true

Publishes to alarms.raw:
{
  "alarm_id": "alarm-uuid-1234",
  "state": "CLEARED",
  "cleared_at": "2025-01-10T15:45:00Z",
  "value": 198,
  "duration_seconds": 900
}

Alerting Service:
  - Resolves PagerDuty incident
  - Sends "All clear" notification
```

**Alarm stored in database**:
```sql
INSERT INTO alarms_history (
  alarm_id, asset_id, type, severity,
  raised_at, acked_at, acked_by, cleared_at, duration_seconds
) VALUES (
  'alarm-uuid-1234', 'offshore_well_12', 'overpressure', 'CRITICAL',
  '2025-01-10T15:30:00Z', '2025-01-10T15:32:00Z', 'alice@example.com',
  '2025-01-10T15:45:00Z', 900
);
```

---

## Message Format Examples

### Telemetry Message (Complete)

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
    "kafka_time": null,
    "timezone": "UTC"
  },
  "clock_skew_ms": 878,
  "metadata": {
    "adapter_id": "adapter_xbee_modbus_001",
    "adapter_version": "1.2.0",
    "pipeline_id": "offshore_well_12",
    "gateway_id": "gateway-rig-alpha",
    "hostname": "rig-alpha.local"
  },
  "schema_version": "1.2.0"
}
```

### Event Message (State Change)

```json
{
  "asset_id": "assembly_line_plc_01",
  "event_type": "motor_state_change",
  "classification": "EVENT",
  "previous_state": {
    "motor_running": false,
    "speed": 0
  },
  "new_state": {
    "motor_running": true,
    "speed": 120
  },
  "timestamps": {
    "device_time": "2025-01-10T08:30:00.123Z",
    "gateway_time": "2025-01-10T08:30:00.150Z"
  },
  "metadata": {
    "adapter_id": "adapter_modbus_tcp_002",
    "pipeline_id": "assembly_line_plc_01"
  }
}
```

### Alarm Message (All States)

**ACTIVE**:
```json
{
  "alarm_id": "alarm-uuid-1234",
  "asset_id": "reactor_01",
  "type": "overpressure",
  "severity": "CRITICAL",
  "state": "ACTIVE",
  "classification": "ALARM",
  "raised_at": "2025-01-10T15:30:00.123Z",
  "acked_at": null,
  "acked_by": null,
  "cleared_at": null,
  "value": 205,
  "threshold": 200,
  "unit": "psi",
  "message": "Pressure exceeded critical threshold",
  "metadata": {...}
}
```

**ACKNOWLEDGED**:
```json
{
  "alarm_id": "alarm-uuid-1234",
  "state": "ACKNOWLEDGED",
  "acked_at": "2025-01-10T15:32:00Z",
  "acked_by": "alice@example.com"
}
```

**CLEARED**:
```json
{
  "alarm_id": "alarm-uuid-1234",
  "state": "CLEARED",
  "cleared_at": "2025-01-10T15:45:00Z",
  "duration_seconds": 900,
  "final_value": 198
}
```

### Log Message (Adapter Event)

```json
{
  "classification": "LOG",
  "log_level": "WARNING",
  "component": "adapter_xbee_modbus_001",
  "message": "XBee communication timeout, retrying...",
  "timestamp": "2025-01-10T12:05:00.456Z",
  "details": {
    "port": "/dev/ttyUSB0",
    "timeout_ms": 5000,
    "retry_attempt": 1,
    "max_retries": 3
  },
  "metadata": {
    "gateway_id": "gateway-rig-alpha",
    "pipeline_id": "offshore_well_12"
  }
}
```

### Aggregated Telemetry (1-minute window)

```json
{
  "asset_id": "reactor_01",
  "parameter": "temperature",
  "unit": "celsius",
  "classification": "TELEMETRY_AGGREGATE",
  "window_start": "2025-01-10T10:00:00Z",
  "window_end": "2025-01-10T10:01:00Z",
  "aggregates": {
    "avg": 342.5,
    "min": 341.8,
    "max": 343.2,
    "stddev": 0.41,
    "count": 600,
    "p50": 342.4,
    "p95": 343.0,
    "p99": 343.1
  },
  "quality_summary": {
    "good_samples": 598,
    "suspect_samples": 2,
    "bad_samples": 0,
    "pct_good": 99.67
  },
  "metadata": {
    "aggregation_version": "1.0.0",
    "source_topic": "telemetry.raw"
  }
}
```

---

**End of Data Flow Documentation**

For architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).
For deployment, see [DEPLOYMENT.md](DEPLOYMENT.md).
