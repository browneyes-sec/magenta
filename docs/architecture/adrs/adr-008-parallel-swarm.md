# ADR-008: Parallel Swarm Execution Model

## Status
Accepted

## Context
The original `SwarmManager.execute_mission()` decomposed missions into tasks and assigned agents, but never actually executed the tasks. Tasks that have no dependencies on each other (e.g., `triage` and `report`) should run in parallel to reduce end-to-end mission latency. Tasks with dependencies (e.g., enrichment after triage) must chain sequentially.

The P1 alert-to-action SLA target is < 10 minutes. Parallel execution is critical for achieving this.

## Decision
Refactor `execute_mission()` to use a two-phase parallel execution model:
1. **Phase 1** — Execute all tasks with no dependencies concurrently via `asyncio.gather`
2. **Phase 2** — Repeatedly resolve tasks whose dependencies are all satisfied, execute those concurrently, repeat until all tasks complete

Task dependency declarations in `decompose_mission()` define the execution order. Circular or missing dependencies raise `AgentError`.

## Rationale
- **Topological execution** guarantees correct ordering: enrichment runs after triage, containment runs after enrichment
- **Maximum parallelism**: independent tasks always run concurrently
- **No framework dependency**: pure asyncio — no Celery, Dask, or workflow engine needed
- **Failure isolation**: `return_exceptions=True` prevents one task failure from killing the mission

## Consequences
- Positive: P50 mission latency for Sev 3 expected < 5 minutes (from ~8+ minutes serial)
- Positive: Failure in one independent task doesn't block other independent tasks
- Negative: Dependency resolution adds complexity vs. simple sequential execution
- Risk: A long-running independent task delays all dependent tasks (mitigated by `asyncio.gather` timeout)

## Compliance
- All tasks must declare dependencies explicitly in `decompose_mission()`
- Circular dependencies must be detected and rejected
- `_execute_single_task()` is the only path for task execution
