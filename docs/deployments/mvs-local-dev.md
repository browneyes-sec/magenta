# Minimum Viable Subset (MVS)

## Hardware Requirements

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 2 cores | 4+ cores |
| RAM | 8 GB | 16+ GB |
| Swap | 8 GB | 4 GB |
| Disk | 20 GB free | 50+ GB free |
| OS | WSL2 / Linux / Docker Desktop | Ubuntu 22.04+ |

## What Runs

| Service | Port | Purpose | Memory |
|---|---|---|---|
| `magenta-redis` | 6379 | Queue/state/cache | 64 MB |
| `magenta-ollama` | 11434 | Local LLM inference | 512 MB |
| `magenta-open-webui` | 3000 | Operator control plane | 256 MB |
| `magenta-pipelines` | 9099 | LangChain pipelines | 128 MB |
| `magenta-otel-collector` | 4317/4318 | Telemetry ingestion | 64 MB |

**Total:** ~1 GB (limits) — fits comfortably in 7.75 GB usable RAM.

## What Does Not Run

| Service | Reason |
|---|---|
| `magenta-mcpo` | MCP Proxy — optional for dev |
| `magenta-open-terminal` | Embedded terminal — not needed |
| `magenta-grafana` | Dashboards — optional |
| `magenta-influxdb` | Time-series DB — optional |
| `magenta-prometheus` | Metrics — optional |
| `magenta-collector-sidecar` | Log collectors — requires cloud credentials |

## Quick Start

```bash
# Clone and enter the repo
git clone https://github.com/browneyes-sec/magenta.git
cd magenta

# Start the MVS stack
docker compose -f soa/docker/docker-compose.mvs.yml up -d

# Pull a tiny model into OLLAMA
docker exec magenta-ollama ollama pull qwen2.5:0.5b

# Verify all services are healthy
docker compose -f soa/docker/docker-compose.mvs.yml ps

# Access Open WebUI
# http://localhost:3000

# Access OLLAMA API
# http://localhost:11434

# Stop the stack
docker compose -f soa/docker/docker-compose.mvs.yml down
```

## Service Details

### 1. Redis (`magenta-redis`)

Core dependency for all other services. Provides:
- Message queue for event pipeline
- Caching for agent state
- Session storage for Open WebUI

```bash
# Verify
docker exec magenta-redis redis-cli ping
# Expected: PONG
```

### 2. OLLAMA (`magenta-ollama`)

Local LLM inference engine. Default model: `qwen2.5:0.5b` (400 MB).

```bash
# List loaded models
docker exec magenta-ollama ollama list

# Pull a larger model (if RAM allows)
docker exec magenta-ollama ollama pull qwen2.5:3b

# Test inference
curl http://localhost:11434/api/generate -d '{"model":"qwen2.5:0.5b","prompt":"Hello"}'
```

### 3. Open WebUI (`magenta-open-webui`)

Operator control plane for agent interaction. Connects to OLLAMA and Pipelines.

```bash
# Verify health
curl -sf http://localhost:3000/health
```

### 4. Pipelines (`magenta-pipelines`)

LangChain pipeline runtime for tool calling and RAG chains.

```bash
# Verify
curl -sf http://localhost:9099/
```

### 5. OTel Collector (`magenta-otel-collector`)

OpenTelemetry Collector for traces, metrics, and logs. Sends to Prometheus (not running in MVS).

```bash
# Verify
curl -sf http://localhost:8888/metrics
```

## Extending to Full Stack

To add optional services later:

```bash
# Add Prometheus + Grafana (monitoring)
docker compose -f soa/docker/docker-compose.mvs.yml \
  -f soa/docker/docker-compose.monitoring.yml up -d

# Add MCP Proxy + Terminal (tool calling)
docker compose -f soa/docker/docker-compose.mvs.yml \
  -f soa/docker/docker-compose.tooling.yml up -d
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| OLLAMA OOM kill | Reduce model size or increase swap |
| Open WebUI won't connect | Ensure OLLAMA is healthy first |
| Redis connection refused | Wait 10s after `up`, check `docker logs magenta-redis` |
| Port 3000 already in use | Change port in compose: `"3001:8080"` |

## Development Workflow

For code development without running services:

```bash
# Install Python deps only
pip install -e ".[dev,test]"

# Run tests (no containers needed)
pytest magnet/ -x

# Run chaos engineering dry-run
python -c "from chaos_engineering.chaos import ChaosEngine; ChaosEngine().run(dry_run=True)"
```
