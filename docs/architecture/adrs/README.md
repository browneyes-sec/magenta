# Architecture Decision Records (ADRs)

This directory documents key architectural decisions made during the Magenta ASOAR platform evolution.

## What is an ADR?

An Architecture Decision Record captures a significant architectural decision, including:
- **Context**: What problem or constraint drove the decision
- **Decision**: What was decided
- **Rationale**: Why this option was chosen over alternatives
- **Consequences**: What trade-offs, risks, and follow-up work result

## ADR Index

| ID | Title | Date | Status |
|----|-------|------|--------|
| 001 | [Registry Triple-Write Pattern](adr-001-registry-triple-write.md) | 2026-07-08 | Accepted |
| 002 | [SOAR Outreach Gate Architecture](adr-002-soar-outreach-gate.md) | 2026-07-08 | Accepted |
| 003 | [EventHub SDK Migration](adr-003-eventhub-sdk-migration.md) | 2026-07-08 | Accepted |
| 004 | [Sensitivity-Aware LLM Routing](adr-004-sensitivity-aware-routing.md) | 2026-07-08 | Accepted |
| 005 | [Circuit Breaker Pattern for Integration Layer](adr-005-circuit-breaker.md) | 2026-07-08 | Accepted |
| 006 | [Idempotency via Azure Table Storage](adr-006-idempotency-store.md) | 2026-07-08 | Accepted |
| 007 | [Approval Gate Architecture](adr-007-approval-gate.md) | 2026-07-08 | Accepted |
| 008 | [Parallel Swarm Execution Model](adr-008-parallel-swarm.md) | 2026-07-08 | Accepted |

## Lifecycle

Each ADR passes through these states:
1. **Proposed** — under review
2. **Accepted** — approved and implemented
3. **Deprecated** — superseded by a later ADR
4. **Superseded** — replaced by a newer decision

## Template

```markdown
# ADR-NNN: Title

## Status
[Proposed | Accepted | Deprecated | Superseded]

## Context
Why is this decision needed? What problem does it solve?

## Decision
What was decided?

## Rationale
Why this approach over alternatives?

## Consequences
What trade-offs, risks, and follow-up work result?

## Compliance
How is this decision enforced in code/review?
```
