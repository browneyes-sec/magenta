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

We define a **Minimum Viable Subset (MVS)** that runs on 8 GB RAM + 8 GB swap:

### MVS Stack (5 services, ~1 GB memory)

| Service | Port | Purpose | Memory Limit |
|---|---|---|---|
| `magenta-redis` | 6379 | Queue/state/cache | 64 MB |
| `magenta-ollama` | 11434 | LLM inference (qwen2.5:0.5b) | 512 MB |
| `magenta-open-webui` | 3000 | Operator control plane | 256 MB |
| `magenta-pipelines` | 9099 | LangChain pipelines | 128 MB |
| `magenta-otel-collector` | 4317/4318 | Telemetry ingestion | 64 MB |

### Excluded from MVS

| Service | Reason |
|---|---|
| `magenta-mcpo` | MCP Proxy — optional for dev |
| `magenta-open-terminal` | Embedded terminal — not needed |
| `magenta-grafana` | Dashboards — optional |
| `magenta-influxdb` | Time-series DB — optional |
| `magenta-prometheus` | Metrics — optional |
| `magenta-collector-sidecar` | Log collectors — requires cloud credentials |

### Deployment

```bash
# Start MVS
docker compose -f soa/docker/docker-compose.mvs.yml up -d

# Pull model
docker exec magenta-ollama ollama pull qwen2.5:0.5b

# Access Open WebUI
http://localhost:3000
```

## Alternatives Considered

1. **GitHub Codespaces** — Free cloud dev env, but requires internet connectivity
2. **Azure/AWS free tier** — Deploy via Terraform, but incurs cost
3. **Minikube with 4 GB RAM** — Only core services, but K8s overhead
4. **Full stack with 16 GB RAM** — Ideal but requires hardware upgrade

## Consequences

- Developers can run the MVS on any 8 GB machine
- Full stack testing happens in CI/CD or cloud environments
- MVS documentation is in `docs/deployments/mvs-local-dev.md`
- ADR-015 captures this decision for future reference

## References

- `soa/docker/docker-compose.mvs.yml` — MVS compose file
- `docs/deployments/mvs-local-dev.md` — MVS documentation
- `architecture/ADR/` — Architecture Decision Records
