# ADR-004: Validation and DLQ Workflow

**Status**: Accepted  
**Date**: 2026-01-29  
**Decision**: Validator as Gateway Runtime module with operator DLQ workflow

---

## Context

Industrial data requires quality validation:
- Range checks (temperature between -50°C and 500°C)
- Rate-of-change detection (sudden spikes)
- Duplicate detection
- Gap detection

Invalid data must be handled without blocking the pipeline.

## Options Considered

### Option A: Validation in Adapter
- Each adapter validates its own data
- No centralized rules

**Pros**: Simple, close to source  
**Cons**: Duplicated logic, no cross-adapter rules, harder to update

### Option B: Validation as Separate Container
- Dedicated validation service
- Consumes raw, produces clean

**Pros**: Isolated, independently scalable  
**Cons**: Container overhead, another component to manage

### Option C: Validation as Gateway Runtime Module
- Built into gateway runtime process
- Consumes raw topics, produces clean topics

**Pros**: Lightweight, shared config, single deployment  
**Cons**: Coupled to runtime, can't scale independently

### Option D: Kafka Streams Application
- Stream processing for validation
- Full Kafka Streams semantics

**Pros**: Powerful, exactly-once semantics  
**Cons**: Complex, JVM dependency, overkill for validation

## Decision

**Option C: Validation as Gateway Runtime module**

## Rationale

1. **Lightweight**: No additional container overhead
2. **Shared config**: Validation rules from same config as adapters
3. **Simple**: Python module, easy to understand and modify
4. **Sufficient**: Validation doesn't need independent scaling at edge

## Quality Codes

Based on IEC 61850 quality model:

| Code | Meaning | Action |
|------|---------|--------|
| GOOD | Passed all validation | Forward to `.clean` topic |
| SUSPECT | Anomalous but within valid range | Forward with flag |
| UNCERTAIN | Low confidence (e.g., clock skew, missing device_time) | Forward with warning |
| BAD | Failed validation | Route to DLQ |

## DLQ Workflow

Dead Letter Queue provides operator visibility and recovery:

```
1. Validator detects BAD data
2. Message written to dlq.telemetry (or dlq.events)
3. Message includes:
   - Original payload
   - Validation failure reason
   - Timestamp
   - Suggested fix (if determinable)

4. Operator views in UI:
   - Filter by gateway, time, error type
   - See original value and failure reason
   - Preview what value would look like if approved

5. Operator actions:
   a) Approve single message → reprocess to .clean topic
   b) Bulk approve → reprocess batch
   c) Update validation rules → reprocess all matching
   d) Discard → remove from DLQ
```

## Consequences

### Positive
- Operators see all rejected data
- Recovery path for false positives
- Validation rules can be updated without data loss
- Clear separation: raw → validate → clean

### Negative
- DLQ can grow large if validation is too strict
- Operator must review (manual step)

### Mitigations
- DLQ retention limit (e.g., 7 days)
- Alerts when DLQ grows beyond threshold
- Bulk actions for common patterns

## Related Decisions
- [ADR-009: Overflow Handling](ADR-009-overflow-handling.md)
