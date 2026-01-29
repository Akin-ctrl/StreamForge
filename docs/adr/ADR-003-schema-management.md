# ADR-003: Schema Management Strategy

**Status**: Accepted  
**Date**: 2026-01-29  
**Decision**: Use Avro serialization with Schema Registry and offline caching

---

## Context

Industrial data must be serialized for transmission through Kafka and to sinks. Key requirements:
- Schema enforcement (prevent garbage data)
- Schema evolution (add fields over time)
- Compact binary format (bandwidth-constrained links)
- Offline operation (gateway may be disconnected)

## Options Considered

### Option A: JSON (No Schema)
- Human-readable
- No schema enforcement

**Pros**: Simple, debuggable  
**Cons**: No validation, verbose, no evolution support

### Option B: JSON Schema
- JSON with schema validation
- Schemas stored separately

**Pros**: Human-readable, validation  
**Cons**: Verbose, slower serialization, limited evolution

### Option C: Avro with Schema Registry
- Binary format with embedded schema ID
- Centralized schema registry
- Strong evolution support

**Pros**: Compact, fast, excellent evolution, industry standard  
**Cons**: Binary (harder to debug), registry dependency

### Option D: Protobuf
- Google's binary format
- Strong typing

**Pros**: Compact, fast, widely used  
**Cons**: Code generation required, less flexible than Avro for dynamic schemas

## Decision

**Option C: Avro with Schema Registry** with mandatory offline caching

## Rationale

1. **Compact binary**: Critical for bandwidth-constrained industrial links
2. **Schema evolution**: BACKWARD compatibility allows adding fields safely
3. **Schema Registry**: Single source of truth for data contracts
4. **Industry standard**: Well-supported by Kafka ecosystem
5. **Offline support**: Cache schemas locally for disconnected operation

## Offline Caching Strategy

```
On gateway startup:
1. Connect to Schema Registry
2. Pull all schemas for configured topics
3. Cache to local file (/data/schemas.cache)

On produce:
1. Check local cache for schema
2. If missing and online → fetch and cache
3. If missing and offline → reject message (fail-safe)

On consume:
1. Schema ID is in message header
2. Look up in local cache
3. If missing and online → fetch and cache
4. If missing and offline → queue for later processing
```

## Consequences

### Positive
- Strong data contracts prevent garbage data
- Schema evolution allows non-breaking changes
- Compact format reduces bandwidth usage
- Offline operation supported

### Negative
- Binary format harder to debug
- Schema Registry is a required component
- Learning curve for Avro

### Mitigations
- Provide CLI tool to decode Avro messages for debugging
- Include Schema Registry in docker-compose
- Document common schema patterns

## Schema Evolution Rules

**Allowed changes**:
- Add optional field with default
- Add new enum value
- Widen numeric type (int → long)

**Breaking changes (rejected by registry)**:
- Remove required field
- Change field type incompatibly
- Rename field

## Related Decisions
- [ADR-001: Edge Buffering](ADR-001-edge-buffering.md)
