# Deployment Guide

**Comprehensive deployment patterns for edge, on-premise, and cloud environments.**

---

## Table of Contents

1. [Deployment Patterns Overview](#deployment-patterns-overview)
2. [Pattern A: Edge + Cloud](#pattern-a-edge--cloud)
3. [Pattern B: Fully On-Premise](#pattern-b-fully-on-premise)
4. [Pattern C: Hybrid (Edge + Data Center + Cloud)](#pattern-c-hybrid-edge--data-center--cloud)
5. [Hardware Requirements](#hardware-requirements)
6. [Network Requirements](#network-requirements)
7. [Installation Procedures](#installation-procedures)
8. [Configuration Management](#configuration-management)
9. [Monitoring & Operations](#monitoring--operations)
10. [Disaster Recovery](#disaster-recovery)

---

## Deployment Patterns Overview

| Pattern | Use Case | Components Location | Network Dependency |
|---------|----------|-------------------|-------------------|
| **Edge + Cloud** | Offshore, remote sites | Edge: Gateway + Local Kafka<br>Cloud: Control + Central Kafka + Sinks | Intermittent OK |
| **On-Premise** | Air-gapped factories, regulatory | All on-prem | LAN only |
| **Hybrid** | Large enterprises | Edge: Gateway<br>DC: Control + Kafka<br>Cloud: Analytics | Tiered |

---

## Pattern A: Edge + Cloud

### Use Cases
- Offshore oil rigs with satellite connectivity
- Remote mining operations
- Distributed renewable energy sites
- Factory floors with unreliable internet

### Architecture

```
┌─────────────────────────────────┐
│  Edge (Offshore Rig)            │
│                                 │
│  ┌─────────────────────┐        │
│  │ Gateway Runtime     │        │
│  └─────────────────────┘        │
│  ┌─────────────────────┐        │
│  │ Local Kafka (1-node)│        │
│  └─────────────────────┘        │
│  ┌─────────────────────┐        │
│  │ Protocol Adapters   │        │
│  │ - Modbus            │        │
│  │ - XBee              │        │
│  └─────────────────────┘        │
│                                 │
│  Network: 4G/Satellite          │
└─────────────┬───────────────────┘
              │ MirrorMaker
              │ (replication)
              ▼
┌─────────────────────────────────┐
│  Cloud (AWS/Azure/GCP)          │
│                                 │
│  ┌─────────────────────┐        │
│  │ Control Plane       │        │
│  │ - API + UI + Copilot│        │
│  └─────────────────────┘        │
│  ┌─────────────────────┐        │
│  │ Central Kafka       │        │
│  │ (3-broker cluster)  │        │
│  └─────────────────────┘        │
│  ┌─────────────────────┐        │
│  │ Sink Services       │        │
│  │ - TimescaleDB       │        │
│  │ - S3 Parquet        │        │
│  │ - ML APIs           │        │
│  └─────────────────────┘        │
└─────────────────────────────────┘
```

### Edge Deployment (Docker Compose)

**File**: `deploy/docker-compose.edge.yml`

```yaml
version: '3.8'

services:
  # Local Kafka (single-node KRaft)
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    container_name: edge-kafka
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@kafka:9093'
      KAFKA_LISTENERS: 'PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://kafka:9092'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT'
      KAFKA_LOG_DIRS: '/var/lib/kafka/data'
      KAFKA_LOG_RETENTION_BYTES: 107374182400  # 100GB max
      KAFKA_LOG_RETENTION_HOURS: 168  # 7 days
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: 'true'
    volumes:
      - /data/kafka:/var/lib/kafka/data
    ports:
      - "9092:9092"
    restart: unless-stopped

  # Gateway Runtime
  gateway_runtime:
    image: streamforge/gateway_runtime:1.0.0
    container_name: gateway_runtime
    environment:
      CONTROL_API_URL: https://control.streamforge.cloud
      GATEWAY_ID: ${GATEWAY_ID}  # Unique ID
      GATEWAY_TOKEN: ${GATEWAY_TOKEN}  # From registration
      LOCAL_KAFKA: kafka:9092
      LOG_LEVEL: INFO
    volumes:
      - /data/gateway:/data
      - /var/run/docker.sock:/var/run/docker.sock  # For adapter management
    depends_on:
      - kafka
    restart: unless-stopped
    network_mode: host  # Access to USB/serial devices

  # MirrorMaker 2.0 (replication to cloud)
  mirrormaker:
    image: confluentinc/cp-kafka:7.5.0
    container_name: mirrormaker
    command: >
      /bin/bash -c "
      echo 'clusters=edge,central' > /tmp/mm2.properties &&
      echo 'edge.bootstrap.servers=kafka:9092' >> /tmp/mm2.properties &&
      echo 'central.bootstrap.servers=${CENTRAL_KAFKA_URL}' >> /tmp/mm2.properties &&
      echo 'central.security.protocol=SASL_SSL' >> /tmp/mm2.properties &&
      echo 'central.sasl.mechanism=PLAIN' >> /tmp/mm2.properties &&
      echo 'central.sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required username=\"${KAFKA_USER}\" password=\"${KAFKA_PASSWORD}\";' >> /tmp/mm2.properties &&
      echo 'edge->central.enabled=true' >> /tmp/mm2.properties &&
      echo 'edge->central.topics=telemetry.*,events.*,alarms.*,logs.*' >> /tmp/mm2.properties &&
      echo 'replication.factor=3' >> /tmp/mm2.properties &&
      /usr/bin/connect-mirror-maker /tmp/mm2.properties
      "
    environment:
      CENTRAL_KAFKA_URL: ${CENTRAL_KAFKA_URL}
      KAFKA_USER: ${KAFKA_USER}
      KAFKA_PASSWORD: ${KAFKA_PASSWORD}
    depends_on:
      - kafka
    restart: unless-stopped

  # Health monitor (optional)
  healthcheck:
    image: streamforge/edge-health:1.0.0
    container_name: edge-health
    environment:
      KAFKA_URL: kafka:9092
      CONTROL_API_URL: https://control.streamforge.cloud
      GATEWAY_ID: ${GATEWAY_ID}
      REPORT_INTERVAL_SEC: 60
    depends_on:
      - kafka
      - gateway_runtime
    restart: unless-stopped
```

**Deployment steps**:

```bash
# 1. Copy to edge device
scp deploy/docker-compose.edge.yml root@edge-gateway:/opt/streamforge/

# 2. SSH to edge device
ssh root@edge-gateway

# 3. Create .env file
cat > /opt/streamforge/.env <<EOF
GATEWAY_ID=gateway-rig-alpha-001
GATEWAY_TOKEN=<token-from-registration>
CENTRAL_KAFKA_URL=pkc-xxxx.region.provider.confluent.cloud:9092
KAFKA_USER=<api-key>
KAFKA_PASSWORD=<api-secret>
EOF

# 4. Start services
cd /opt/streamforge
docker-compose -f docker-compose.edge.yml up -d

# 5. Verify
docker-compose logs -f gateway_runtime
```

### Cloud Deployment (Kubernetes)

**File**: `deploy/k8s/cloud/control-plane.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: control-api
  namespace: streamforge
spec:
  replicas: 3
  selector:
    matchLabels:
      app: control-api
  template:
    metadata:
      labels:
        app: control-api
    spec:
      containers:
      - name: api
        image: streamforge/control-api:1.0.0
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: url
        - name: KAFKA_BOOTSTRAP
          value: "kafka.streamforge.svc.cluster.local:9092"
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: jwt-secret
              key: secret
        ports:
        - containerPort: 8000
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: control-api
  namespace: streamforge
spec:
  type: LoadBalancer
  selector:
    app: control-api
  ports:
  - port: 443
    targetPort: 8000
    protocol: TCP
```

**Kafka deployment** (using Confluent Operator or Strimzi):

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: streamforge-kafka
  namespace: streamforge
spec:
  kafka:
    version: 3.5.0
    replicas: 3
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
      - name: tls
        port: 9093
        type: internal
        tls: true
        authentication:
          type: scram-sha-512
    config:
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      transaction.state.log.min.isr: 2
      default.replication.factor: 3
      min.insync.replicas: 2
    storage:
      type: persistent-claim
      size: 500Gi
      class: fast-ssd
  zookeeper:
    replicas: 3
    storage:
      type: persistent-claim
      size: 100Gi
      class: fast-ssd
  entityOperator:
    topicOperator: {}
    userOperator: {}
```

---

## Pattern B: Fully On-Premise

### Use Cases
- Air-gapped factories (no internet)
- Regulatory compliance (data cannot leave premises)
- Low-latency requirements

### Architecture

```
┌───────────────────────────────────────────┐
│  On-Premise Data Center                   │
│                                           │
│  ┌──────────────┐    ┌─────────────────┐ │
│  │ Control Plane│    │ Central Kafka   │ │
│  │ API + UI     │    │ (3-broker)      │ │
│  └──────────────┘    └─────────────────┘ │
│                                           │
│  ┌──────────────┐    ┌─────────────────┐ │
│  │ Sinks        │    │ Gateway Runtime │ │
│  │ TimescaleDB  │    │ (on IPC near    │ │
│  │ PostgreSQL   │    │  devices)       │ │
│  └──────────────┘    └─────────────────┘ │
│                                           │
│  Network: Internal LAN only               │
└───────────────────────────────────────────┘
```

### Deployment (Docker Compose - All-in-One)

**File**: `deploy/docker-compose.onprem.yml`

```yaml
version: '3.8'

services:
  # PostgreSQL (control database)
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: streamforge
      POSTGRES_USER: streamforge
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # Kafka (3-broker cluster)
  kafka-1:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093'
      KAFKA_LISTENERS: 'PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://kafka-1:9092'
      KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_LOG_DIRS: '/var/lib/kafka/data'
    volumes:
      - kafka-1-data:/var/lib/kafka/data

  kafka-2:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_NODE_ID: 2
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093'
      KAFKA_LISTENERS: 'PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://kafka-2:9092'
      KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_LOG_DIRS: '/var/lib/kafka/data'
    volumes:
      - kafka-2-data:/var/lib/kafka/data

  kafka-3:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_NODE_ID: 3
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093'
      KAFKA_LISTENERS: 'PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://kafka-3:9092'
      KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_LOG_DIRS: '/var/lib/kafka/data'
    volumes:
      - kafka-3-data:/var/lib/kafka/data

  # Schema Registry
  schema-registry:
    image: confluentinc/cp-schema-registry:7.5.0
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: 'kafka-1:9092,kafka-2:9092,kafka-3:9092'
    depends_on:
      - kafka-1
      - kafka-2
      - kafka-3
    ports:
      - "8081:8081"

  # Control API
  control-api:
    image: streamforge/control-api:1.0.0
    environment:
      DATABASE_URL: postgresql://streamforge:${POSTGRES_PASSWORD}@postgres:5432/streamforge
      KAFKA_BOOTSTRAP: kafka-1:9092,kafka-2:9092,kafka-3:9092
      SCHEMA_REGISTRY_URL: http://schema-registry:8081
    depends_on:
      - postgres
      - kafka-1
    ports:
      - "8000:8000"

  # UI
  ui:
    image: streamforge/ui:1.0.0
    environment:
      API_URL: http://control-api:8000
    ports:
      - "80:80"
    depends_on:
      - control-api

  # TimescaleDB (sink)
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_DB: telemetry
      POSTGRES_USER: telemetry
      POSTGRES_PASSWORD: ${TIMESCALE_PASSWORD}
    volumes:
      - timescale-data:/var/lib/postgresql/data
    ports:
      - "5433:5432"

  # Sink service (Kafka → TimescaleDB)
  sink-timescaledb:
    image: streamforge/sink-timescaledb:1.0.0
    environment:
      KAFKA_BOOTSTRAP: kafka-1:9092,kafka-2:9092,kafka-3:9092
      KAFKA_TOPICS: telemetry.clean,events.clean
      TIMESCALE_URL: postgresql://telemetry:${TIMESCALE_PASSWORD}@timescaledb:5432/telemetry
    depends_on:
      - kafka-1
      - timescaledb

volumes:
  postgres-data:
  kafka-1-data:
  kafka-2-data:
  kafka-3-data:
  timescale-data:
```

**Deployment**:

```bash
# Deploy entire stack
docker-compose -f deploy/docker-compose.onprem.yml up -d

# Access UI
open http://localhost
```

---

## Pattern C: Hybrid (Edge + Data Center + Cloud)

### Architecture

```
Edge (Factory Floor)
  ↓ (LAN, low latency)
On-Prem Data Center
  ├─ Control Plane
  ├─ Central Kafka
  └─ Critical Sinks (real-time)
  ↓ (WAN, batch)
Cloud
  ├─ S3 (long-term storage)
  ├─ ML/Analytics
  └─ Business Intelligence
```

### Data Flow Routing

```yaml
# Routing rules
telemetry.raw → On-Prem Kafka
telemetry.clean → On-Prem TimescaleDB (real-time dashboard)
telemetry.1min → Cloud S3 (historical analysis)

alarms.* → On-Prem only (low latency critical)
events.* → On-Prem + Cloud

logs.* → Cloud (non-critical)
```

---

## Hardware Requirements

### Edge Gateway

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores (x86_64 or ARM64) | 4 cores |
| RAM | 4GB | 8GB |
| Disk | 100GB SSD | 250GB NVMe SSD |
| Network | 1 Mbps uplink | 10 Mbps |
| OS | Ubuntu 20.04+ or Debian 11+ | Ubuntu 22.04 LTS |

**Supported hardware**:
- Industrial PCs (Dell Edge Gateway, HPE Edgeline)
- Raspberry Pi 4 (8GB model) for light workloads
- ARM-based gateways (NVIDIA Jetson for ML edge)

### Control Plane (Cloud)

| Service | CPU | RAM | Disk |
|---------|-----|-----|------|
| Control API | 2 cores | 4GB | 20GB |
| UI | 1 core | 2GB | 10GB |
| PostgreSQL | 2 cores | 8GB | 100GB SSD |
| Kafka (per broker) | 4 cores | 16GB | 500GB SSD |

### On-Premise

**Small deployment** (1-10 gateways):
- 1 server: 16 cores, 64GB RAM, 2TB SSD

**Medium deployment** (10-50 gateways):
- 3 servers: 32 cores, 128GB RAM, 4TB SSD each

**Large deployment** (50+ gateways):
- Kubernetes cluster (min 5 nodes)

---

## Network Requirements

### Edge → Cloud

| Pattern | Bandwidth | Latency | Uptime |
|---------|-----------|---------|--------|
| Continuous (factory) | 1-10 Mbps | < 100ms | 99% |
| Intermittent (offshore) | 256 Kbps | < 500ms | 70%+ (buffering handles rest) |

**Protocols**:
- HTTPS (443) for Control API
- Kafka over TLS (9093)
- Optional: VPN/IPSec tunnel

### Firewall Rules (Outbound from Edge)

```
Allow: TCP 443 → control.example.com (Control API)
Allow: TCP 9093 → kafka.example.com (Kafka replication)
Allow: UDP 123 → pool.ntp.org (NTP for time sync)
Allow: UDP 53 → DNS
Block: All inbound (except local management)
```

---

## Installation Procedures

### Edge Gateway Installation

**Automated installer**:

```bash
# Download installer
curl -fsSL https://get.streamforge.io | bash

# Or manual installation
wget https://releases.streamforge.io/gateway/v1.0.0/streamforge-gateway-installer.sh
chmod +x streamforge-gateway-installer.sh
./streamforge-gateway-installer.sh

# Follow prompts:
# 1. Gateway ID (unique identifier)
# 2. Control API URL
# 3. Registration token
# 4. Local Kafka disk limit (default 100GB)
```

**What it does**:
1. Installs Docker & Docker Compose
2. Downloads edge stack images
3. Generates TLS certificates
4. Registers with Control Plane
5. Starts services
6. Configures autostart (systemd)

**Post-installation**:

```bash
# Check status
sudo systemctl status streamforge-gateway

# View logs
sudo journalctl -u streamforge-gateway -f

# Restart
sudo systemctl restart streamforge-gateway
```

### Control Plane Installation (Cloud)

**Kubernetes (Helm)**:

```bash
# Add Helm repo
helm repo add streamforge https://charts.streamforge.io
helm repo update

# Install
helm install streamforge streamforge/streamforge \
  --namespace streamforge \
  --create-namespace \
  --set global.domain=streamforge.example.com \
  --set kafka.replicas=3 \
  --set kafka.storage.size=500Gi \
  --set postgres.password=<secure-password>

# Check status
kubectl get pods -n streamforge
```

**Docker Compose** (for testing):

```bash
git clone https://github.com/streamforge/streamforge.git
cd streamforge/deploy
cp .env.example .env
# Edit .env with your settings
docker-compose up -d
```

---

## Configuration Management

### Environment Variables

**Edge Gateway**:
```bash
GATEWAY_ID=gateway-factory-01
CONTROL_API_URL=https://api.streamforge.example.com
GATEWAY_TOKEN=<jwt-token>
LOCAL_KAFKA_DISK_LIMIT_GB=100
LOG_LEVEL=INFO
```

**Control Plane**:
```bash
DATABASE_URL=postgresql://user:pass@postgres:5432/streamforge
KAFKA_BOOTSTRAP=kafka-1:9092,kafka-2:9092,kafka-3:9092
SCHEMA_REGISTRY_URL=http://schema-registry:8081
JWT_SECRET=<random-secret>
SMTP_HOST=smtp.example.com  # For email alerts
```

### Secrets Management

**HashiCorp Vault integration**:

```bash
# Store Kafka credentials
vault kv put secret/streamforge/kafka \
  username=admin \
  password=<secure-password>

# Adapter config references secrets
{
  "source": {
    "opcua_username": "${vault:secret/streamforge/opcua/username}",
    "opcua_password": "${vault:secret/streamforge/opcua/password}"
  }
}
```

---

## Monitoring & Operations

### Metrics Collection

**Prometheus scraping**:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'streamforge-gateways'
    static_configs:
      - targets:
          - gateway-1.example.com:9090
          - gateway-2.example.com:9090
    metrics_path: '/metrics'

  - job_name: 'streamforge-kafka'
    static_configs:
      - targets:
          - kafka-1:9092
          - kafka-2:9092
          - kafka-3:9092
```

**Key metrics**:

```
# Gateway health
gateway_adapters_running{gateway_id="gateway-1"}
gateway_kafka_lag_seconds{gateway_id="gateway-1"}
gateway_disk_usage_percent{gateway_id="gateway-1"}

# Adapter metrics
adapter_readings_total{adapter_id="adapter-modbus-001"}
adapter_errors_total{adapter_id="adapter-modbus-001",type="connection"}

# Kafka metrics
kafka_consumer_lag{topic="telemetry.raw",consumer_group="sink-timescaledb"}
```

### Grafana Dashboards

Pre-built dashboards available at `deploy/grafana/dashboards/`:
- `gateway-overview.json` - Fleet-wide gateway health
- `kafka-performance.json` - Kafka cluster metrics
- `data-quality.json` - DLQ rates, validation failures

### Alerting Rules

```yaml
# alerts.yml
groups:
  - name: streamforge
    rules:
      - alert: GatewayOffline
        expr: up{job="streamforge-gateways"} == 0
        for: 5m
        annotations:
          summary: "Gateway {{ $labels.gateway_id }} offline"

      - alert: KafkaLagHigh
        expr: gateway_kafka_lag_seconds > 300
        for: 10m
        annotations:
          summary: "Gateway {{ $labels.gateway_id }} replication lag > 5min"

      - alert: DiskUsageHigh
        expr: gateway_disk_usage_percent > 85
        for: 15m
        annotations:
          summary: "Gateway {{ $labels.gateway_id }} disk > 85%"
```

---

## Disaster Recovery

### Backup Strategy

**What to backup**:
1. **Control Database** (PostgreSQL) - configuration state
2. **Kafka topics** (if needed for compliance)
3. **TimescaleDB** (telemetry data)

**Backup procedure**:

```bash
# Control DB backup (daily)
pg_dump -h postgres-host -U streamforge -d streamforge | \
  gzip > streamforge-control-$(date +%Y%m%d).sql.gz

# Upload to S3
aws s3 cp streamforge-control-$(date +%Y%m%d).sql.gz \
  s3://backups/streamforge/

# Kafka topic backup (optional, for compliance)
kafka-mirror-maker \
  --consumer.config source.properties \
  --producer.config backup.properties \
  --whitelist "telemetry.clean|alarms.*"
```

### Recovery Procedures

**Scenario 1: Edge gateway failure**

```bash
# 1. Provision new hardware
# 2. Run installer with SAME gateway_id
./streamforge-gateway-installer.sh

# 3. Gateway re-registers with Control Plane
# 4. Control Plane pushes last known config
# 5. Adapters restart automatically
# 6. Data collection resumes (no historical data lost, still in central Kafka)
```

**Scenario 2: Central Kafka failure**

```bash
# With replication factor 3, losing 1 broker:
# → Automatic failover, no data loss

# Losing all brokers (catastrophic):
# 1. Edge gateways buffer locally (up to disk limit)
# 2. Restore Kafka cluster from backups
# 3. Restart MirrorMaker on edge gateways
# 4. Data syncs automatically
```

**Scenario 3: Control Plane failure**

```bash
# Edge gateways continue operating (data plane unaffected)
# 1. Restore Control DB from backup
# 2. Redeploy Control API/UI
# 3. Gateways reconnect automatically
# 4. Configuration state restored
```

### High Availability

**Kafka HA** (3+ brokers):
```
Replication factor: 3
Min in-sync replicas: 2
Tolerate: 1 broker failure
```

**Control API HA** (Kubernetes):
```yaml
replicas: 3
podAntiAffinity: hard (different nodes)
livenessProbe: /health
```

**Database HA**:
- PostgreSQL: Streaming replication (primary + 2 replicas)
- TimescaleDB: Multi-node setup or managed service (AWS RDS, Azure Database)

---

**End of Deployment Guide**

For architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).
For security, see [SECURITY.md](SECURITY.md).
