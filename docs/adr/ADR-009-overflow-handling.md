# ADR-009: Overflow Handling

**Status**: Accepted  
**Date**: 2026-01-29  
**Decision**: Tiered overflow with priority-based eviction

---

## Context

Edge gateways have limited disk space (typically 100-500GB). When sinks are offline for extended periods:
- Local Kafka fills up
- New data cannot be written
- Risk of data loss

We needed a strategy for handling disk exhaustion.

## Options Considered

### Option A: Block Producers
- Stop accepting writes when full
- Adapters block until space available

**Pros**: Simple, no data loss of existing data  
**Cons**: Current data lost, adapters may crash

### Option B: Oldest-First Eviction
- Delete oldest data to make room
- FIFO regardless of content

**Pros**: Simple, preserves recent data  
**Cons**: May delete critical alarms

### Option C: Priority-Based Eviction
- Assign priority to topics
- Evict lowest-priority first

**Pros**: Protects critical data  
**Cons**: More complex, priority tuning needed

### Option D: Tiered Overflow
- Multiple strategies applied in sequence
- Compress → Downsample → Evict → Block

**Pros**: Maximizes data preservation  
**Cons**: Most complex

## Decision

**Option D: Tiered overflow with priority-based eviction**

## Rationale

1. **Compress first**: Saves 50-70% space with minimal information loss
2. **Downsample before delete**: Keep aggregates, discard raw
3. **Priority eviction**: Alarms are never deleted before telemetry
4. **Block as last resort**: Better than crashing

## Tier Strategy

| Disk Usage | Action |
|------------|--------|
| 0-70% | Normal operation |
| 70-80% | **Alert**. Compress old Kafka segments. |
| 80-90% | **Aggressive downsample**. Delete raw telemetry older than 1 hour, keep aggregates. |
| 90-95% | **Priority eviction**. Delete oldest data, lowest priority first. |
| 95%+ | **Block producers**. Critical alert. Stop accepting new data. |

## Topic Priority

| Priority | Topics | Eviction Order |
|----------|--------|----------------|
| Critical | `alarms.*`, `dlq.*` | Never evicted |
| High | `events.*`, `telemetry.1min` | Last to be evicted |
| Medium | `telemetry.1s` | After low priority |
| Low | `telemetry.raw` | First to be evicted |

**Key rule**: Alarms are NEVER evicted. If disk is 95% full and only alarms remain, block producers.

## Implementation

```python
# Gateway Runtime disk monitor (runs every 60s)
def check_disk_overflow():
    usage = get_disk_usage_percent()
    
    if usage < 70:
        return  # Normal
    
    if usage < 80:
        alert("Disk usage at 70%+, compressing")
        compress_old_segments()
        return
    
    if usage < 90:
        alert("Disk usage at 80%+, downsampling")
        delete_raw_older_than(hours=1)
        return
    
    if usage < 95:
        alert("Disk usage at 90%+, evicting low priority")
        evict_by_priority(target_percent=85)
        return
    
    # 95%+
    critical_alert("Disk full, blocking producers")
    block_kafka_producers()
```

## Overflow Event

When data is evicted, emit an event for audit:

```json
{
  "event_type": "buffer_overflow",
  "timestamp": "2026-01-29T10:00:00Z",
  "topic": "telemetry.raw",
  "action": "evicted",
  "bytes_freed": 5368709120,
  "oldest_evicted": "2026-01-22T00:00:00Z",
  "newest_evicted": "2026-01-25T12:00:00Z"
}
```

This event is written to `dlq.overflow` (high priority, not evicted).

## Consequences

### Positive
- Maximizes data preservation
- Critical data (alarms) protected
- Clear escalation path
- Audit trail of evictions

### Negative
- Complex logic
- Raw data may be lost in overflow scenarios

### Mitigations
- UI shows overflow events
- Alerts at each tier threshold
- Recommend adequate disk sizing

## Disk Sizing Guidance

| Data Rate | Offline Duration | Recommended Disk |
|-----------|------------------|------------------|
| 1 MB/s | 1 day | 100 GB |
| 1 MB/s | 7 days | 700 GB |
| 10 MB/s | 1 day | 1 TB |

## Related Decisions
- [ADR-001: Edge Buffering](ADR-001-edge-buffering.md)
- [ADR-008: Failure Modes](ADR-008-failure-modes.md)
