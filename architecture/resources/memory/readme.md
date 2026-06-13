# Memory Architecture & Sizing

## Component Overview

Magenta's memory budget spans:

- **FastAPI workers** — request handling, JSON serialization, Pydantic validation
- **Orchestration engine** — mission state, task queues, agent contexts
- **OLLAMA** — model weights + KV cache (see [GPU guide](../gpu/readme.md))
- **Elasticsearch** — JVM heap for indexing and querying
- **PostgreSQL** — shared_buffers, connection memory
- **Redis** — in-memory state store
- **Agent processes** — prompt/response buffers, tool call results

## Per-Component Memory Budget

### Control Plane (Non-GPU)

| Component | Base | Per Unit | Formula |
|---|---|---|---|
| FastAPI worker | 128 MB | +50 MB per concurrent request | `128 + (50 × reqs_per_worker)` |
| Orchestration engine | 256 MB | +100 MB per active mission | `256 + (100 × missions)` |
| Agent runtime (per agent) | 64 MB | +prompt_size × 4 (overhead) | `64 + (prompt_kb × 4)` |
| PostgreSQL | 256 MB | +25% of dataset in shared_buffers | `max(256, dataset × 0.25)` |
| Redis | 128 MB | +state_per_mission × 50 KB | `128 + (missions × 0.05)` |
| Elasticsearch JVM heap | 1 GB | +50% of data for filesystem cache | `max(1 GB, data_size × 0.5)` |

### Model Serving (OLLAMA)

| Model | Quantization | RAM (load) | VRAM (inference) |
|---|---|---|---|
| qwen2.5:7b | FP16 | 14 GB | 14 GB |
| qwen2.5:7b | Q4_K_M | 4.5 GB | 6 GB |
| mistral:7b | Q4_K_M | 4.5 GB | 6 GB |
| mixtral:8x7b | Q4_K_M | 26 GB | 28 GB |
| qwen2.5:32b | Q4_K_M | 18 GB | 23 GB |

## Production Sizing Profiles

### Small (dev/test, < 10 alerts/day)

| Component | RAM |
|---|---|
| Control plane | 4 GB |
| OLLAMA (2× 7B Q4) | 8 GB |
| Elasticsearch | 4 GB |
| PostgreSQL | 2 GB |
| Redis | 1 GB |
| **Total** | **~20 GB** |

### Medium (production, 50-200 alerts/day)

| Component | RAM |
|---|---|
| Control plane | 8 GB |
| OLLAMA (3× 7B Q4 + 1× 32B Q4) | 32 GB |
| Elasticsearch | 16 GB |
| PostgreSQL | 8 GB |
| Redis | 4 GB |
| **Total** | **~70 GB** on 2-3 nodes |

### Large (enterprise, 500+ alerts/day)

| Component | RAM |
|---|---|
| Control plane (HA) | 16 GB |
| OLLAMA cluster (multi-node) | 128+ GB |
| Elasticsearch cluster (3 nodes) | 64 GB each |
| PostgreSQL (primary + replica) | 16 GB each |
| Redis cluster | 8 GB |
| **Total** | **~300+ GB** distributed |

## Swap Strategy

- **Never swap model weights** — OLLAMA will OOM if VRAM + swap is insufficient
- **Acceptable swap targets**: Elasticsearch filesystem cache, PostgreSQL shared_buffers, idle agent context
- **Disable swap** on GPU nodes; enable with `vm.swappiness=10` on data nodes

## Configuration

```bash
# OLLAMA — limit model concurrency
OLLAMA_NUM_PARALLEL=2

# PostgreSQL — tuned for Magenta workload
MAGENTA_SQL__POOL_SIZE=10
MAGENTA_SQL__MAX_OVERFLOW=20

# Elasticsearch — heap size via ES_JAVA_OPTS
ES_JAVA_OPTS="-Xms8g -Xmx8g"

# Redis — max memory
redis-cli CONFIG SET maxmemory 4gb
```

## Monitoring

| Metric | Alert |
|---|---|
| System RAM > 85% used | Warning |
| System RAM > 95% used | Critical |
| OLLAMA OOM count | Immediate |
| Elasticsearch heap > 80% | Warning |
| PostgreSQL connection count > pool_size | Warning |
| Swap usage > 0 on GPU nodes | Critical |
