# ADR-013: Synchronous Path Retained as Emergency Fallback Only

**Status:** Accepted
**Date:** 2026-06-16
**Deciders:** Architecture Board / Senior Integrations Engineer
**TOGAF ADM Phase:** G (Implementation Governance)
**WAF Pillar:** Reliability · Operational Excellence

## Context

The legacy `SwarmManagerAgent.run_mission()` (magenta/agents/manager.py:55-75) executes tasks sequentially in a simple for-loop as a fallback when the DAG executor is unavailable or for debugging. DTP-02 §4.2 mandates this path be retained but strictly limited to emergency use.

## Decision

The synchronous sequential executor (`SwarmManagerAgent.run_mission`) remains in the codebase but:
1. Is **never** the default path for production missions
2. Requires explicit opt-in via `mission.governance.execution_mode = "sync_fallback"`
3. Emits a `WARNING` log with `fallback_reason` when invoked
4. Is excluded from SLO measurements (availability, latency)
5. Has a dedicated runbook: `docs/runbooks/sync-fallback.md`

## Rationale

- **Safety net**: If DAG executor has a bug (cycle detection, deadlock), SOC can still process critical alerts
- **Debugging**: Deterministic sequential execution aids root-cause analysis
- **Compliance**: Audit trail shows fallback was exceptional, not standard

## Consequences

### Positive
- Zero-downtime fallback for mission-critical alerts
- No architectural dependency on DAG executor maturity

### Negative / Trade-offs
- Code duplication: two execution paths to maintain
- Sync path lacks parallelism, retries, observability richness
- Risk of accidental fallback becoming default (mitigated by governance flag + log alert)

### Risks
- **Risk**: Team uses sync path for convenience, bypassing DAG benefits
  **Mitigation**: CI check (`architecture-compliance.yml`) flags PRs adding `execution_mode: sync_fallback` without Architecture Board approval
- **Risk**: Sync path bit-rots unnoticed
  **Mitigation**: Monthly chaos test includes "force sync fallback" scenario

## Compliance

DTP-02 §4.2, DTP-03 §5.3 (Chaos Engineering Plan), AC-03 3.7 (Chaos test scenario 7)

## Verification

- CI gate: grep for `execution_mode.*sync_fallback` in playbook YAMLs → fail if found without `x-approved-by: arch-board`
- Chaos test: Kill DAG executor pod, verify sync fallback activates, alerts fire, mission completes
- Runbook review: `docs/runbooks/sync-fallback.md` exists and tested quarterly