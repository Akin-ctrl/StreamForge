# ADR-001: Edge Buffering Strategy

**Status**: Accepted  
**Date**: 2026-01-29  
**Decision**: Use embedded Kafka (KRaft mode) for edge buffering

---

## Context

Industrial gateways must buffer data locally when network connectivity to sinks is unavailable. This is critical for:
- Offshore installations with satellite links
- Remote sites with intermittent connectivity
- Network outages lasting hours to days

We needed to decide how to implement reliable local buffering.

## Options Considered

### Option A: Custom File-Based Buffer
- Write messages to local files
- Custom replay logic
- Custom durability guarantees

**Pros**: Lightweight, no dependencies  
**Cons**: Reinventing the wheel, error-prone, no standard tooling

### Option B: SQLite Queue
- Store messages in SQLite
- FIFO queue pattern

**Pros**: Simple, embedded  
**Cons**: Not designed for streaming, no consumer offset tracking, limited throughput

### Option C: Embedded Kafka (KRaft mode)
- Single-node Kafka cluster per gateway
- KRaft mode (no ZooKeeper required)
- Standard Kafka protocol

**Pros**: Proven durability, standard tooling, replay capability, consumer offset tracking  
**Cons**: Higher resource usage (~512MB RAM)

### Option D: Redis Streams
- Use Redis as a message broker
- Lightweight streaming

**Pros**: Fast, lightweight  
**Cons**: Not designed for long-term persistence, less mature than Kafka

## Decision

**Option C: Embedded Kafka (KRaft mode)**

## Rationale

1. **Proven durability**: Kafka is battle-tested for exactly this use case
2. **Standard protocol**: Sinks use standard Kafka consumers, no custom code
3. **Replay capability**: Any sink can replay from any offset
4. **Consumer offsets**: Track exactly what each sink has processed
5. **No central Kafka required**: Each gateway is fully independent
6. **Backpressure handling**: Native flow control

The ~512MB RAM overhead is acceptable for industrial gateway hardware (typically 4-16GB RAM).

## Consequences

### Positive
- Reliable buffering with minimal custom code
- Sinks can use any Kafka client library
- Standard CLI tools for debugging
- Natural fit for multi-sink architecture

### Negative
- Higher memory footprint than lightweight alternatives
- Kafka operational knowledge required
- Disk I/O requirements for durability

### Mitigations
- Configure appropriate memory limits
- Document Kafka tuning for edge deployment
- Provide default configurations for common hardware

## Related Decisions
- [ADR-009: Overflow Handling](ADR-009-overflow-handling.md)
