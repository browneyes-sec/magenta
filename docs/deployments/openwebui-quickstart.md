# Open WebUI Quickstart

## Prerequisites

- Docker & Docker Compose v2
- Magenta repo cloned and `uv pip install -e ".[dev]"` completed
- 16GB+ RAM recommended (OLLAMA + 10 containers)

## Start the Stack

```bash
# From repo root
docker compose -f soa/docker/docker-compose.openwebui.yml up -d
#     ____   ___  _  _    ___
#    / ___| / _ \| \| |  / _ \ _ __   ___
#   | |  _| | | | .` | | | | | '_ \ / _ \
#   | |_| | |_| | |\  | | |_| | | | |  __/
#    \____|\___/|_| \_|  \___/|_| |_|\___|
#
# Starting 10 services...
#  - magenta-ollama
#  - magenta-open-webui
#  - magenta-pipelines
#  - magenta-mcpo
#  - magenta-open-terminal
#  - magenta-otel-collector
#  - magenta-prometheus
#  - magenta-grafana
#  - magenta-influxdb
#  - magenta-redis
```

## Verify Services

```bash
# All containers running
docker compose -f soa/docker/docker-compose.openwebui.yml ps

# Check logs
docker compose -f soa/docker/docker-compose.openwebui.yml logs -f magenta-open-webui
```

## Access the UIs

| Service | URL | Credentials |
|---|---|---|
| Open WebUI | http://localhost:3000 | Admin setup on first login |
| Grafana | http://localhost:3001 | `admin` / `magenta` |
| Prometheus | http://localhost:9090 | — |

## Run Magenta Regression Suite

```bash
# From repo root, in the magenta venv
magenta state regression

# Expected: 66 passed (or current count)
```

## Test the Approval Card

```bash
# Trigger a high-risk action to create a pending approval
magenta dictator deploy triage  # (or any other command)

# Open Open WebUI at http://localhost:3000
# Type: approval_card
# You should see an interactive HTML card with Approve/Deny buttons
```

## Generate Artifacts

In Open WebUI chat:

```
generate_artifact mission_throughput
generate_artifact threat_analytics
generate_artifact directive_timeline
generate_artifact policy_status
generate_artifact dead_letter
```

## Access Dictator CLI

Through Open Terminal at http://localhost:8082:

```bash
magenta dictator status
magenta dictator oversight
magenta dictator policies
magenta dictator directives --limit 20
```

## Stop the Stack

```bash
docker compose -f soa/docker/docker-compose.openwebui.yml down
# Add -v to also remove volumes (deletes OLLAMA models and data)
```



## Troubleshooting

| Symptom | Check |
|---|---|
| Open WebUI won't start | `docker logs magenta-ollama` — OLLAMA may need more RAM |
| Pipeline tools return errors | Ensure `magenta` is importable in the pipeline container |
| Approval card shows no buttons | CORS — Open WebUI must be on the same network as the API |
| Grafana dashboards empty | Prometheus needs 5-10 min to collect first metrics |
| Redis connection refused | `docker compose restart magenta-redis` |
