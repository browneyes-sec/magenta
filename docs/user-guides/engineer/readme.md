# Engineer User Guide

## Audience

DevOps engineers, platform engineers, and SREs deploying and operating the Magenta ASOAR framework in production.

## Table of Contents

1. [Installation & Setup](#installation--setup)
2. [Configuration Management](#configuration-management)
3. [Deployment Architectures](#deployment-architectures)
4. [CI/CD Integration](#cicd-integration)
5. [Infrastructure as Code](#infrastructure-as-code)
6. [Secrets Management](#secrets-management)
7. [Scaling & Performance Tuning](#scaling--performance-tuning)
8. [Monitoring & Observability](#monitoring--observability)
9. [Backup & Disaster Recovery](#backup--disaster-recovery)

---

## Installation & Setup

### Prerequisites

- Python 3.12+
- OLLAMA (for local model inference)
- PostgreSQL 16+ (production) or SQLite (development)
- Elasticsearch 8.x (production)
- Redis 7.x (production)

### Quick Start

```bash
# Install Magenta
pip install -e .

# Verify installation
magenta --version

# Initialize configuration
mkdir -p config data
magenta -c config/dev.yaml health
```

### Running the API Server

```bash
# Development (reload on changes)
uvicorn magenta.api.server:create_app --reload --host 0.0.0.0 --port 8000

# Production (Gunicorn + Uvicorn workers)
gunicorn magenta.api.server:create_app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --timeout 120
```

## Configuration Management

Environment-based configuration with Pydantic Settings:

| Variable | Default | Description |
|---|---|---|
| `MAGENTA_ENV` | `dev` | Runtime environment |
| `MAGENTA_SQL__URL` | `sqlite+aiosqlite:///data/magenta.db` | Database connection |
| `MAGENTA_ELASTIC__HOSTS` | `["http://localhost:9200"]` | Elasticsearch nodes |
| `MAGENTA_MODELS__OLLAMA_HOST` | `http://localhost:11434` | OLLAMA endpoint |
| `MAGENTA_EVENTHUB__CONNECTION_STRING` | — | Azure Event Hubs |
| `MAGENTA_LAKE__CONNECTION_STRING` | — | Data Lake connection |

## Deployment Architectures

Refer to the [Web Architecture Guide](../../docs/usage/web-architecture.md) for topology details.

### Docker Compose (Single Host)

```yaml
# docker-compose.yml
version: "3.9"
services:
  api:
    build: .
    ports: ["8000:8000"]
    depends_on: [postgres, redis, ollama]
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: magenta
      POSTGRES_PASSWORD: ${DB_PASSWORD}
  redis:
    image: redis:7-alpine
  ollama:
    image: ollama/ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Kubernetes

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: magenta-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: magenta-api
  template:
    metadata:
      labels:
        app: magenta-api
    spec:
      containers:
        - name: api
          image: magenta:latest
          ports:
            - containerPort: 8000
          env:
            - name: MAGENTA_ENV
              value: "prod"
            - name: MAGENTA_SQL__URL
              valueFrom:
                secretKeyRef:
                  name: magenta-db
                  key: url
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
          readinessProbe:
            httpGet:
              path: /readyz
              port: 8000
```

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy Magenta
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: pytest

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploy to production cluster"
```

## Secrets Management

```yaml
# .env.production (never committed)
MAGENTA_SQL__URL="postgresql+asyncpg://..."
MAGENTA_ELASTIC__PASSWORD="..."
MAGENTA_MODELS__OPENROUTER_KEY="..."
MAGENTA_MODELS__GEMINI_KEY="..."
MAGENTA_EVENTHUB__CONNECTION_STRING="..."
```

In Kubernetes:

```bash
kubectl create secret generic magenta-secrets \
    --from-literal=db-url="postgresql+asyncpg://..." \
    --from-literal=es-password="..."
```

## Monitoring & Observability

### Key Metrics to Export

```python
# Prometheus / OpenTelemetry metrics
from opentelemetry import metrics

mission_counter = metrics.create_counter(
    "magenta.missions.total",
    description="Total missions created",
    unit="1",
)
mission_duration = metrics.create_histogram(
    "magenta.mission.duration_seconds",
    description="Mission execution duration",
    unit="s",
)
agent_turn_counter = metrics.create_counter(
    "magenta.agent.turns",
    description="Agent turns executed",
)
model_latency = metrics.create_histogram(
    "magenta.model.latency_ms",
    description="Model inference latency",
    unit="ms",
)
```

### Dashboards

| Platform | Dashboard | Metrics |
|---|---|---|
| Grafana | Mission Overview | Mission rate, duration, success/fail rate |
| Grafana | Agent Performance | Turns per agent, latency, error rate |
| Grafana | Model Health | OLLAMA queue depth, VRAM, response time |
| Kibana | Registry Explorer | Activity events, audit trail |
| Azure Monitor | Infrastructure | CPU, memory, network, disk |

## Backup & Disaster Recovery

| Component | Backup Strategy | RPO | RTO |
|---|---|---|---|
| PostgreSQL | pg_dump daily + WAL streaming | 1 hour | 30 min |
| Elasticsearch | Snapshot to blob storage | 6 hours | 1 hour |
| Redis | RDB every 5 min | 5 min | 5 min |
| Data Lake | Geo-redundant storage (LRS/GRS) | Instant | Instant |
| Config | Git (version controlled) | — | — |

### Recovery Runbook

```bash
# 1. Restore PostgreSQL
pg_restore -d magenta latest.dump

# 2. Restore Elasticsearch snapshots
curl -X POST "localhost:9200/_snapshot/magenta-archive/snapshot_20260613/_restore"

# 3. Rebuild Redis from RDB
redis-server --appendonly no --dbfilename dump.rdb
```
