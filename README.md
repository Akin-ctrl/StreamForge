# StreamForge

**A Kafka-centric industrial data gateway that dynamically connects OT systems to modern IT, cloud, and AI platforms with zero data loss, full decoupling, and real-time observability.**

## Overview

Industrial Data Gateway is a protocol-agnostic streaming platform that bridges the gap between Operational Technology (OT) and Information Technology (IT) environments. Built on Apache Kafka as the authoritative data backbone, it provides reliable, replayable, and scalable data flows across manufacturing, oil & gas, utilities, and smart factory environments.

## Key Features

- **Zero Data Loss**: Kafka-first architecture ensures data durability even during network, database, or cloud outages
- **Protocol Agnostic**: Native support for Modbus, OPC UA, MQTT, XBee, LoRa, and custom industrial protocols
- **Dynamic Configuration**: Runtime reconfiguration without redeploying gateways or restarting services
- **Edge + Cloud**: Works fully offline, on-premise, or in hybrid cloud deployments
- **Semantic Data Classification**: First-class support for telemetry, events, alarms, and logs
- **Real-time Observability**: Unified view of data flows, health metrics, and system topology
- **AI-Powered Copilot**: Intelligent assistant for configuration optimization and anomaly detection

## Architecture

The system is composed of two distinct planes:

### Control Plane (Configuration & Orchestration)
- **Config & Control API**: REST API for managing pipelines, gateways, and configurations
- **UI**: Web interface for visual pipeline creation and monitoring
- **AI Copilot**: Intelligent assistant for optimization and troubleshooting
- **Control Database**: PostgreSQL for configuration state and audit trails

### Data Plane (Data Movement)
- **Gateway Runtime**: Edge daemon that manages protocol adapters and local buffering
- **Protocol Adapters**: Containerized plugins for industrial protocols (Modbus, OPC UA, MQTT, XBee)
- **Kafka Clusters**: Distributed log as the system of record (edge + central)
- **Sink Services**: Independent consumers for databases, cloud platforms, and analytics

## Project Structure

```
industrial-data-gateway/
├── docs/                      # Comprehensive documentation
│   ├── ARCHITECTURE.md        # System architecture and design decisions
│   ├── DATA_FLOW.md          # End-to-end data flow documentation
│   ├── DEPLOYMENT.md         # Deployment patterns and guides
│   └── SECURITY.md           # Security model and best practices
├── control-plane/            # Configuration & control API (FastAPI)
├── gateway-runtime/          # Edge daemon (Python)
├── adapters/                 # Protocol adapter implementations
│   ├── modbus/              # Modbus TCP/RTU adapter
│   ├── opcua/               # OPC UA adapter
│   ├── mqtt/                # MQTT adapter
│   └── xbee-modbus/         # XBee to Modbus virtual adapter
├── ui/                      # Web interface (React/TypeScript)
├── copilot/                 # AI Copilot service (Python)
├── sinks/                   # Sink service implementations
├── schemas/                 # Avro/JSON schema definitions
└── deploy/                  # Docker Compose and Kubernetes manifests
```

## Core Principles

### 1. Kafka is the System of Record
All industrial data **must** first be written to Kafka. Everything else is downstream and replaceable. This eliminates:
- Data loss during sink failures
- Tight coupling between data producers and consumers
- Vendor lock-in
- Unrecoverable failures

### 2. Control Plane ≠ Data Plane
Configuration logic is completely separated from data movement. The control plane defines *what should happen*, the data plane *makes it happen*.

### 3. Semantic Data Classification
Data is classified at ingestion:
- **Telemetry**: Continuous numeric measurements (pressure, temperature, vibration)
- **Events**: Discrete state changes (valve opened, motor stopped)
- **Alarms**: Events with severity and lifecycle (overpressure, fire detected)
- **Logs**: Operational messages (adapter crashed, connection lost)

### 4. Edge-First Design
Gateways operate autonomously with local buffering. Network failures don't stop data collection.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- Kafka cluster (local or remote)

### Local Development Setup

```bash
# Clone and navigate
cd ~/industrial-data-gateway

# Start Kafka and dependencies
docker-compose -f deploy/docker-compose.dev.yml up -d

# Start control plane
cd control-plane
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Start UI
cd ../ui
npm install
npm run dev

# Start gateway runtime (on edge device or locally)
cd ../gateway-runtime
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m gateway_runtime.main
```

## Use Cases

### Smart Manufacturing
- PLCs → Edge Gateway → Local Kafka → Central Kafka → Analytics
- Real-time production monitoring with zero data loss
- Predictive maintenance via ML pipelines

### Offshore Oil & Gas
- Sensors → LoRa/XBee → Edge Gateway → Local Kafka (buffered during outages)
- Automatic sync to cloud when satellite link restored
- Critical alarm routing to PagerDuty

### Utilities & Power Plants
- SCADA systems → OPC UA → Kafka → TimescaleDB + Cloud Analytics
- Digital twin synchronization
- Regulatory compliance audit trails

## Documentation

- [Architecture & Design](docs/ARCHITECTURE.md) - Deep dive into system design and decisions
- [Data Flow](docs/DATA_FLOW.md) - End-to-end data flow with examples
- [Deployment Guide](docs/DEPLOYMENT.md) - Edge, on-prem, and cloud deployment patterns
- [Security Model](docs/SECURITY.md) - Authentication, authorization, and encryption
- [Protocol Adapter Development](adapters/README.md) - How to build custom adapters
- [API Reference](control-plane/README.md) - Control API documentation

## Comparison

| Feature | This Platform | SCADA/Ignition | IoT Cloud Platforms | Custom Scripts |
|---------|---------------|----------------|---------------------|----------------|
| Industrial Protocols | ✅ Native | ✅ Via plugins | ❌ Limited | ⚠️ Manual |
| Kafka-First | ✅ Core design | ❌ Optional | ❌ Optional | ❌ No |
| Zero Data Loss | ✅ Guaranteed | ⚠️ Database-dependent | ⚠️ Cloud-dependent | ❌ No |
| Edge Autonomy | ✅ Full offline | ⚠️ Limited | ❌ Cloud-required | ⚠️ Manual |
| Runtime Reconfiguration | ✅ Yes | ❌ Requires restart | ⚠️ Limited | ❌ Redeploy |
| Vendor Neutral | ✅ Yes | ❌ Proprietary | ❌ Cloud lock-in | ✅ Yes |
| AI/ML Ready | ✅ Stream-native | ⚠️ Via exports | ⚠️ Via integrations | ❌ Manual |

## Roadmap

**Phase 1: Core Platform** (Current)
- ✅ Architecture design complete
- 🚧 Control plane API
- 🚧 Gateway runtime engine
- 🚧 Basic protocol adapters (Modbus, MQTT)
- 🚧 UI for pipeline configuration

**Phase 2: Reliability & Scale**
- Schema registry integration
- Edge buffering with overflow handling
- Multi-gateway fleet management
- Advanced sink services

**Phase 3: Intelligence**
- AI Copilot integration
- Anomaly detection
- Auto-configuration suggestions
- Predictive buffering

**Phase 4: Enterprise Features**
- Advanced RBAC
- Multi-tenancy
- SaaS deployment option
- Marketplace for adapters

## License

[To be determined]

## Contributing

[To be determined]

## Support

[To be determined]
