# CPU Architecture & Sizing

## Component Overview

Magenta's control plane comprises several processes that share the CPU budget:

- **FastAPI server** (Gunicorn + Uvicorn workers) — serves REST API, webhook receivers, auto-docs
- **Orchestration engine** — async mission runner, agent assignment, task dispatch
- **Agent runtime** — per-agent process executing LLM calls, tool invocations, evidence processing
- **OLLAMA** — model inference server (see [GPU guide](../gpu/readme.md) for inference; CPU used for prompt processing and fallback)
- **SQL/NoSQL/Elastic clients** — connection pool threads, serialization

## Sizing Baseline

### Development / Single-host

| Process | Cores | Notes |
|---|---|---|
| FastAPI (1 worker) | 1 | Uvicorn single-process |
| Orchestration | 1 | Async I/O bound |
| OLLAMA (7B model) | 4 | CPU-based inference fallback |
| PostgreSQL / SQLite | 1 | Local dev |
| Total | 6 | Shared on laptop |

### Production — Dedicated Control Plane

| Component | Cores | Scaling |
|---|---|---|
| FastAPI (4 workers) | 4 | Horizontal via container replicas |
| Orchestration | 2 | One per availability zone |
| Agent runtime pool | 4 | Scale with concurrent mission count |
| Redis | 2 | Separate node recommended |
| PostgreSQL | 4 | Read replica for reporting |
| OLLAMA | 8-16 | Separate GPU node (see GPU guide) |
| **Control plane total** | **16** | 3-node cluster minimum |

## Bottleneck Analysis

| Scenario | Bottleneck | Mitigation |
|---|---|---|
| High alert volume (100+/min) | API workers | Scale to 8+ workers, add auto-scaling |
| Complex mission decomposition | Orchestration | Decrease `max_concurrent_agents` per mission |
| Large context prompts (>32K tokens) | Agent runtime | Increase worker count, reduce per-agent turns |
| Concurrent tool executions | Connection pool | Tune `pool_size` and `max_overflow` in SQL |


## Configuration

```yaml
# config/default.yaml — CPU-related settings
sql:
  pool_size: 5           # connections per worker
  max_overflow: 10       # burst connections

orchestration:
  max_concurrent_missions: 10
  max_tasks_per_mission: 50
  agent_timeout_seconds: 120
```

Environment variables:

```bash
# Worker count (FastAPI)
MAGENTA_WORKERS=4

# OLLAMA threads (CPU inference)
OLLAMA_NUM_THREADS=8
```

## Monitoring

| Metric | Alert Threshold | Severity |
|---|---|---|
| CPU utilization > 80% | 5 min sustained | Warning |
| CPU utilization > 90% | 2 min sustained | Critical |
| API p99 latency > 2 s | 1 min sustained | Warning |
| Agent queue depth > 50 | 30 s sustained | Warning |
