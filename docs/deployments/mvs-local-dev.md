# Minimum Viable Subset (MVS)

## Hardware Requirements

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 2 cores | 4+ cores |
| RAM | 8 GB | 16+ GB |
| Swap | 8 GB | 4 GB |
| Disk | 20 GB free | 50+ GB free |
| OS | WSL2 / Linux / Docker Desktop | Ubuntu 22.04+ |

## Integration Tiers

| Tier | Services | Memory | Use Case |
|---|---|---|---|
| **MVS** | Redis, OLLAMA, Open WebUI, Pipelines, OTel, MCPO | ~1 GB | UI + LLM + pipelines |
| **Core** | + API, Worker, Scheduler, Agent-Ops | +576 MB | Full agent runtime |
| **Full** | + Grafana, Prometheus, InfluxDB, Collector | +768 MB | Observability |

Progressive enhancement: start with MVS, add Core when pipeline tools are needed, add Full for monitoring.

---

## MVS Stack (6 services)

| Service | Port | Purpose | Memory |
|---|---|---|---|
| `magenta-redis` | 6379 | Queue/state/cache | 64 MB |
| `magenta-ollama` | 11434 | Local LLM inference | 512 MB |
| `magenta-open-webui` | 3000 | Operator control plane | 256 MB |
| `magenta-pipelines` | 9099 | LangChain pipelines | 128 MB |
| `magenta-otel-collector` | 4317/4318 | Telemetry ingestion | 64 MB |
| `magenta-mcpo` | 8001 | MCP Proxy (HTTP transport) | 64 MB |

**Total:** ~1 GB (limits) — fits in 7.75 GB usable RAM.

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

# Access MCPO (MCP Proxy)
# http://localhost:8001

# Stop the stack
docker compose -f soa/docker/docker-compose.mvs.yml down
```

## Progressive Enhancement

### Adding Core Services (Agent Runtime)

```bash
# Start MVS + Core (API, Worker, Scheduler, Agent-Ops)
docker compose -f soa/docker/docker-compose.mvs.yml \
  -f soa/docker/docker-compose.core.yml up -d

# Initialize state (register agents, create sample mission)
docker exec magenta-api bash /init-state.sh

# Verify pipeline tools work
# Open http://localhost:3000 and type: dictator_status
```

Core services add:
- `magenta-api` (8000) — REST API for external integrations
- `magenta-worker` — Mission execution via DAG executor
- `magenta-scheduler` — Cron + approval polling
- `magenta-agent-ops` (50060) — Agent orchestration MCP

### Adding Full Stack (Observability)

```bash
# Start MVS + Core + Monitoring
docker compose -f soa/docker/docker-compose.mvs.yml \
  -f soa/docker/docker-compose.core.yml \
  -f soa/docker/docker-compose.monitoring.yml up -d
```

Monitoring adds:
- `magenta-grafana` (3001) — Dashboards (user: `admin`, pass: `magenta`)
- `magenta-prometheus` (9090) — Metrics storage
- `magenta-influxdb` (32768) — Time-series data

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

### 6. MCPO (`magenta-mcpo`)

MCP Proxy for tool calling. Uses HTTP transport to avoid Python module dependencies.

```bash
# Verify
curl -sf http://localhost:8001/docs
```

## Pipeline Tools

After starting MVS, these tools are available in Open WebUI:

| Tool | Command | Description |
|---|---|---|
| `dictator_status` | Type in chat | Show framework status |
| `check_pending_approvals` | Type in chat | List pending approvals |
| `policy_list` | Type in chat | Show active policies |
| `connector_health` | Type in chat | Check connector status |
| `registry_search` | Type in chat | Search agent registry |

**Note:** Some tools require Core services (API, Worker) to be running. Without them, you'll see import errors.

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

## Troubleshooting

| Symptom | Fix |
|---|---|
| OLLAMA OOM kill | Reduce model size or increase swap |
| Open WebUI won't connect | Ensure OLLAMA is healthy first |
| Redis connection refused | Wait 10s after `up`, check `docker logs magenta-redis` |
| Port 3000 already in use | Change port in compose: `"3001:8080"` |
| MCPO exited | Check logs: `docker logs magenta-mcpo` |
| Pipeline tools fail | Start Core services (API, Worker) |
| `dictator_status` error | Run `init-state.sh` to register agents |

## Architecture References

- `architecture/ADR/ADR-015-minimum-viable-subset.md` — Architecture decision
- `soa/docker/docker-compose.mvs.yml` — MVS compose file
- `soa/docker/docker-compose.core.yml` — Core services compose
- `soa/docker/init-state.sh` — State initialization script
