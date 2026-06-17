# ADR-015: Minimum Viable Subset (MVS) for Local Development

## Status

Accepted

## Context

Developers and QA analysts need to run the Magenta ASOAR platform locally for testing and development. The full 11-service stack requires 12-15 GB RAM, which exceeds the 7.75 GB usable RAM available on developer workstations (i3-1005G1, 8 GB RAM, 8 GB swap).

Running the full stack on constrained hardware causes:
- OOM kills (especially OLLAMA with large models)
- Constant swap thrashing (10x slower than RAM)
- Container startup failures
- Developer frustration and lost productivity

## Decision

We define a **Minimum Viable Subset (MVS)** with progressive enhancement tiers:

### Integration Tiers

| Tier | Services | Memory | Use Case |
|---|---|---|---|
| **MVS** | Redis, OLLAMA, Open WebUI, Pipelines, OTel, MCPO | ~1 GB | UI + LLM + pipelines |
| **Core** | + API, Worker, Scheduler, Agent-Ops | +576 MB | Full agent runtime |
| **Full** | + Grafana, Prometheus, InfluxDB, Collector | +768 MB | Observability |

### MVS Stack (6 services, ~1 GB memory)

| Service | Port | Purpose | Memory Limit |
|---|---|---|---|
| `magenta-redis` | 6379 | Queue/state/cache | 64 MB |
| `magenta-ollama` | 11434 | LLM inference (qwen2.5:0.5b) | 512 MB |
| `magenta-open-webui` | 3000 | Operator control plane | 256 MB |
| `magenta-pipelines` | 9099 | LangChain pipelines | 128 MB |
| `magenta-otel-collector` | 4317/4318 | Telemetry ingestion | 64 MB |
| `magenta-mcpo` | 8001 | MCP Proxy (HTTP transport) | 64 MB |

### Core Stack (additional 4 services, +576 MB)

| Service | Port | Purpose | Memory Limit |
|---|---|---|---|
| `magenta-api` | 8000 | FastAPI REST API | 256 MB |
| `magenta-worker` | — | Mission execution (DAG executor) | 128 MB |
| `magenta-scheduler` | — | Cron + approval polling | 64 MB |
| `magenta-agent-ops` | 50060 | Agent orchestration MCP | 128 MB |

### Full Stack (additional 3 services, +768 MB)

| Service | Port | Purpose | Memory Limit |
|---|---|---|---|
| `magenta-grafana` | 3001 | Operational dashboards | 256 MB |
| `magenta-prometheus` | 9090 | Metrics storage | 256 MB |
| `magenta-influxdb` | 32768 | Time-series data | 256 MB |

### Memory Budget (8 GB RAM)

| Tier | Cumulative | Fits in 7.75 GB |
|---|---|---|
| MVS | 1 GB | Yes |
| MVS + Core | 1.6 GB | Yes |
| MVS + Core + Full | 2.4 GB | Yes |
| Buffer (OS + Docker) | ~2 GB | — |
| **Total** | **~4.4 GB** | **Yes** |

### Deployment

```bash
# MVS only
docker compose -f soa/docker/docker-compose.mvs.yml up -d

# MVS + Core (full agent runtime)
docker compose -f soa/docker/docker-compose.mvs.yml \
  -f soa/docker/docker-compose.core.yml up -d

# MVS + Core + Full (observability)
docker compose -f soa/docker/docker-compose.mvs.yml \
  -f soa/docker/docker-compose.core.yml \
  -f soa/docker/docker-compose.monitoring.yml up -d

# Initialize state (after Core is up)
docker exec magenta-api bash /init-state.sh
```

### MCPO Transport

MCPO uses HTTP transport (not stdio) to avoid Python module dependencies in the MCPO container. MCP servers are accessed via the Magenta API's HTTP endpoints.

```json
{
  "mcpServers": {
    "registry": {
      "transport": "http",
      "url": "http://magenta-api:8000/mcp/registry"
    }
  }
}
```

### State Initialization

The `init-state.sh` script runs on first startup to:
1. Register 6 base agents (triage, enrichment, containment, investigation, compliance, reporting)
2. Instantiate the Dictator agent
3. Create a sample mission for pipeline testing

## Alternatives Considered

1. **GitHub Codespaces** — Free cloud dev env, but requires internet connectivity
2. **Azure/AWS free tier** — Deploy via Terraform, but incurs cost
3. **Minikube with 4 GB RAM** — Only core services, but K8s overhead
4. **Full stack with 16 GB RAM** — Ideal but requires hardware upgrade

## Consequences

- Developers can run the MVS on any 8 GB machine
- Progressive enhancement allows adding services as needed
- Full stack testing happens in CI/CD or cloud environments
- MVS documentation is in `docs/deployments/mvs-local-dev.md`
- ADR-015 captures this decision for future reference

## References

- `soa/docker/docker-compose.mvs.yml` — MVS compose file
- `soa/docker/docker-compose.core.yml` — Core services compose
- `soa/docker/mcpo-config.mvs.json` — MCPO HTTP transport config
- `soa/docker/init-state.sh` — State initialization script
- `docs/deployments/mvs-local-dev.md` — MVS documentation
- `architecture/ADR/` — Architecture Decision Records
