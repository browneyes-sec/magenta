# ADR-012: Parallel DAG Execution Replacing Sequential Chain

**Status:** Accepted
**Date:** 2026-06-16
**Deciders:** Architecture Board / Senior Integrations Engineer
**TOGAF ADM Phase:** G (Implementation Governance)
**WAF Pillar:** Performance Efficiency · Reliability

## Context

The original mission execution model (DTP-01, DTP-02) used a sequential chain: triage → enrich → contain → investigate → compliance → report. This creates unnecessary latency for independent tasks and single-points-of-failure. DTP-02 §3 introduced a DAG-based executor (`magenta/orchestration/dag_executor.py`) supporting topological scheduling and parallel task execution with configurable concurrency.

## Decision

Adopt the `DAGExecutor` as the default mission execution engine. All playbooks define stages with explicit `depends_on` edges. The executor runs ready tasks in parallel up to `max_concurrency` (default 5), with retries and exponential backoff per node.

## Rationale

- **Latency reduction**: Independent tasks (e.g., enrich + triage for separate alerts) run concurrently. Benchmark target: severity-4 mission < 10s P95.
- **Fault isolation**: Task failure only blocks dependent tasks; siblings continue.
- **Resource efficiency**: Concurrency limit prevents thundering herd on LLM APIs.
- **Observability**: Each DAG node emits structured spans/metrics (mission_id, task_id, role, latency).

## Consequences

### Positive
- Mission duration scales with DAG depth, not width
- Clear dependency graph enables replay from failed node
- KEDA can scale agent deployments per-role based on queue depth

### Negative / Trade-offs
- Playbook authors must declare dependencies explicitly (no implicit ordering)
- Cyclic dependency detection adds validation step (Kahn's algorithm in `DAGExecutor._validate_dag`)
- Debugging parallel traces requires correlation_id propagation

### Risks
- **Risk**: Implicit sequential assumptions in existing playbooks
  **Mitigation**: Migration script converts linear `tasks[]` to single-dependency stages; validation in CI

## Compliance

DTP-02 §3 (DAG Executor), DTP-03 §3.3 (Performance Efficiency), AC-03 3.4 (Prometheus recording rules for mission latency)

## Verification

- Unit test: `magnet/test_orchestration/test_dag_executor.py` validates parallel execution, cycle detection, retry logic
- CI gate: `architecture-compliance.yml` schema-compliance job validates `AutomationActivity` schema_version
- Benchmark: `make bench-mission` runs severity-4 playbook, asserts P95 < 10s