# Health API

## `GET /api/v1/health`

Full system health check. Pings all registered agents, model backends, and storage layers.

```json
{
  "status": "healthy",
  "timestamp": "2026-06-13T14:30:00Z",
  "version": "0.1.0",
  "checks": {
    "agents": {
      "status": "healthy",
      "count": 6,
      "by_role": {"triage_agent": 1, "enrich_agent": 1, "contain_agent": 2, "swarm_manager": 1, "report_agent": 1}
    },
    "models": {
      "status": "healthy",
      "available": 4
    },
    "pipeline": {
      "status": "healthy",
      "message": "Event Hubs stub — no actual connection"
    }
  }
}
```

| Status | Meaning |
|---|---|
| `healthy` | All components operational |
| `degraded` | Some components down (non-critical) |
| `down` | Critical components unavailable |

## `GET /api/v1/health/agents`

Agent-specific health: lists every agent with status, role, and assigned model.

## `GET /api/v1/health/models`

Model backend health: pings all configured model providers.

```json
{
  "status": "healthy",
  "count": 4,
  "models": [
    {"name": "ollama_qwen", "provider": "ollama", "model": "qwen2.5:7b"},
    {"name": "ollama_mistral", "provider": "ollama", "model": "mistral:7b"}
  ]
}
```

## Health Check Endpoints for Load Balancers

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health` | Full application health |
| `GET /healthz` | Liveness probe (returns 200) |
| `GET /readyz` | Readiness probe (checks dependencies) |
