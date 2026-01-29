# ADR-002: Protocol Adapter Architecture

**Status**: Accepted  
**Date**: 2026-01-29  
**Decision**: Deploy protocol adapters as Docker containers

---

## Context

StreamForge must support multiple industrial protocols (Modbus, OPC UA, MQTT, XBee, LoRa, etc.). Each protocol has different:
- Library dependencies
- Runtime requirements
- Update cycles
- Security considerations

We needed to decide how to package and deploy protocol adapters.

## Options Considered

### Option A: Monolithic Runtime
- All adapters compiled into gateway runtime
- Single process handles all protocols

**Pros**: Simple deployment, shared memory  
**Cons**: Version coupling, one crash affects all, large binary, security concerns

### Option B: Plugin Architecture
- Dynamic loading of adapter plugins
- Shared process, separate modules

**Pros**: Lighter weight than containers  
**Cons**: Still version coupled, complex plugin interface, shared memory security

### Option C: Docker Containers
- Each adapter runs in its own container
- Communicates via Kafka

**Pros**: Full isolation, independent versioning, security boundaries, standard tooling  
**Cons**: Higher resource overhead, container orchestration complexity

### Option D: Separate Processes (no containers)
- Each adapter is a separate OS process
- Managed by gateway runtime

**Pros**: Isolation without container overhead  
**Cons**: No standard packaging, dependency conflicts, harder to manage

## Decision

**Option C: Docker containers**

## Rationale

1. **Isolation**: Crashes in one adapter don't affect others
2. **Security**: Each adapter runs with minimal privileges
3. **Versioning**: Update adapters independently
4. **Resource limits**: Docker enforces memory/CPU limits (bulkhead pattern)
5. **Portability**: Same container works on any gateway
6. **Standard interface**: Config via environment, health via HTTP, output via Kafka

## Consequences

### Positive
- Clear security boundaries between protocols
- Independent release cycles per adapter
- Easy to add new protocols without touching core
- Bulkhead pattern prevents resource starvation

### Negative
- Container orchestration complexity
- ~50MB overhead per container
- Network latency between containers (minimal for localhost)

### Mitigations
- Gateway runtime handles container lifecycle
- Use lightweight base images (python:slim, alpine)
- All communication over localhost

## Adapter Contract

Every adapter must:
1. Accept config via `ADAPTER_CONFIG` environment variable (JSON)
2. Publish to Kafka topics specified in config
3. Expose `GET /health` endpoint
4. Expose `GET /metrics` endpoint (Prometheus format)
5. Log structured JSON to stdout
6. Handle SIGTERM for graceful shutdown

## Related Decisions
- [ADR-005: Sink Architecture](ADR-005-sink-architecture.md)
