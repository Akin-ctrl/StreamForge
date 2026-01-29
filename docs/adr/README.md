# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for key design decisions in StreamForge.

## What is an ADR?

An ADR documents a significant architectural decision, including:
- **Context**: Why the decision was needed
- **Options**: What alternatives were considered
- **Decision**: What was chosen
- **Consequences**: Trade-offs and implications

## ADR Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](ADR-001-edge-buffering.md) | Edge Buffering Strategy | Accepted |
| [ADR-002](ADR-002-protocol-adapters.md) | Protocol Adapter Architecture | Accepted |
| [ADR-003](ADR-003-schema-management.md) | Schema Management Strategy | Accepted |
| [ADR-004](ADR-004-validation-dlq.md) | Validation and DLQ Workflow | Accepted |
| [ADR-005](ADR-005-sink-architecture.md) | Sink Architecture | Accepted |
| [ADR-006](ADR-006-gateway-autonomy.md) | Gateway Autonomy | Accepted |
| [ADR-007](ADR-007-authentication.md) | Authentication Model | Accepted |
| [ADR-008](ADR-008-failure-modes.md) | Failure Modes and Recovery | Accepted |
| [ADR-009](ADR-009-overflow-handling.md) | Overflow Handling | Accepted |
| [ADR-010](ADR-010-copilot-mcp.md) | Copilot Tools-First Approach | Accepted |

## Key Decisions Summary

### Data Path
- **Edge Buffering**: Embedded Kafka (KRaft mode) per gateway
- **Serialization**: Avro with Schema Registry
- **Adapters & Sinks**: Docker containers with standard contract
- **Overflow**: Tiered strategy (compress → downsample → evict by priority)

### Architecture
- **Gateway Autonomy**: Full offline capability after first boot
- **Validation**: Module in Gateway Runtime, BAD → DLQ with operator workflow
- **Failure Handling**: Restart + bulkhead isolation + circuit breaker

### Operations
- **Authentication**: JWT for gateways, built-in + OAuth for users
- **AI Copilot**: MCP tools-first, built-in Copilot optional

## Creating New ADRs

When making a significant architectural decision:

1. Copy the template:
   ```bash
   cp ADR-TEMPLATE.md ADR-0XX-short-title.md
   ```

2. Fill in all sections

3. Add to the index above

4. Get team review

## ADR Statuses

| Status | Meaning |
|--------|---------|
| Proposed | Under discussion |
| Accepted | Decision made, implementing |
| Deprecated | Superseded by another ADR |
| Rejected | Considered but not chosen |
