# Magenta ASOAR — Minimal Production Environment

Standardized minimal required resources for establishing the Agentic SOAR system.
Cloud-agnostic, open-source-first stack with production hardening.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL INGRESS                            │
│                    (NGINX / Traefik / Cloud LB)                    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                     CONTROL PLANE (K8s)                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │   API Server │ │  MCP Bridge  │ │   Web GW     │               │
│  │   (FastAPI)  │ │   (gRPC)     │ │  (Reverse P) │               │
│  │   :8000      │ │   :8080      │ │   :8081      │               │
│  └──────────────┘ └──────────────┘ └──────────────┘               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │  Agent Ops   │ │ Orchestrator │ │  Scheduler   │               │
│  │  :50060      │ │  :50061      │ │  :50062      │               │
│  └──────────────┘ └──────────────┘ └──────────────┘               │
└────────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                      DATA PLANE                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │   Qdrant     │ │   OLLAMA     │ │    Redis     │               │
│  │  (Vector DB) │ │  (Embeddings)│ │   (Cache)    │               │
│  │   :6333/34   │ │   :11434     │ │   :6379      │               │
│  └──────────────┘ └──────────────┘ └──────────────┘               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │ Elasticsearch│ │ PostgreSQL   │ │    MinIO     │               │
│  │  (Search)    │ │  (SQL)       │ │  (Object)    │               │
│  │   :9200      │ │   :5432      │ │   :9000      │               │
│  └──────────────┘ └──────────────┘ └──────────────┘               │
└────────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                   OBSERVABILITY                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │  OTel Collect│ │   Prometheus │ │    Grafana   │               │
│  │   :4317/18   │ │   :9090      │ │   :3000      │               │
│  └──────────────┘ └──────────────┘ └──────────────┘               │
│  ┌──────────────┐ ┌──────────────┐                                 │
│  │    Tempo     │ │   Loki       │                                 │
│  │   :3200      │ │   :3100      │                                 │
│  └──────────────┘ └──────────────┘                                 │
└────────────────────────────────────────────────────────────────────┘
```

---

## Minimal Production Requirements

### Compute Resources

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit | Replicas |
|-----------|-------------|-----------|----------------|--------------|----------|
| API Server | 1000m | 2000m | 1Gi | 2Gi | 2 |
| MCP Bridge | 500m | 1000m | 512Mi | 1Gi | 2 |
| Agent Ops | 1000m | 2000m | 1Gi | 2Gi | 1 |
| Orchestrator | 500m | 1000m | 512Mi | 1Gi | 1 |
| Web Gateway | 250m | 500m | 256Mi | 512Mi | 2 |
| Workers | 500m | 1000m | 512Mi | 1Gi | 2 |
| **Total (min)** | **4 CPU** | **8 CPU** | **4 Gi** | **8 Gi** | **10** |

### Data Plane Resources

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit | Storage |
|-----------|-------------|-----------|----------------|--------------|---------|
| Qdrant | 1000m | 2000m | 2Gi | 4Gi | 50Gi SSD |
| OLLAMA | 2000m | 4000m | 4Gi | 8Gi | 20Gi |
| Redis | 500m | 1000m | 512Mi | 1Gi | 5Gi |
| Elasticsearch | 1000m | 2000m | 2Gi | 4Gi | 100Gi SSD |
| PostgreSQL | 500m | 1000m | 1Gi | 2Gi | 50Gi SSD |
| MinIO | 500m | 1000m | 512Mi | 1Gi | 100Gi |
| **Total (min)** | **5.5 CPU** | **11 CPU** | **10 Gi** | **20 Gi** | **325 Gi** |

### Observability Resources

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit | Storage |
|-----------|-------------|-----------|----------------|--------------|---------|
| OTel Collector | 250m | 500m | 256Mi | 512Mi | - |
| Prometheus | 500m | 1000m | 1Gi | 2Gi | 50Gi |
| Grafana | 250m | 500m | 256Mi | 512Mi | 10Gi |
| Tempo | 250m | 500m | 512Mi | 1Gi | 50Gi |
| Loki | 250m | 500m | 512Mi | 1Gi | 50Gi |
| **Total (min)** | **1.5 CPU** | **3 CPU** | **2.5 Gi** | **5 Gi** | **160 Gi** |

---

## Infrastructure Summary

### Cluster Requirements

| Tier | CPU Cores | RAM | Storage | Nodes |
|------|-----------|-----|---------|-------|
| **Minimal** | 12 | 16 Gi | 500 Gi | 3 |
| **Recommended** | 24 | 32 Gi | 1 Ti | 5 |
| **Production** | 48 | 64 Gi | 2 Ti | 7 |

### Cloud-Agnostic Requirements

| Requirement | Specification |
|-------------|---------------|
| Container Runtime | containerd 1.7+ |
| Kubernetes | 1.28+ |
| Load Balancer | MetalLB (bare metal) or cloud provider LB |
| Ingress | NGINX Ingress Controller 1.9+ |
| Storage Class | SSD-backed (gp3, Premium_LRS, pd-ssd) |
| DNS | CoreDNS 1.11+ |
| Network Policy | Calico or Cilium |

---

## Software Dependencies

### Core Runtime

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.11+ | Runtime |
| uv | Latest | Package management |
| Node.js | 20 LTS | Web UI (optional) |

### Container Images

| Image | Version | Purpose |
|-------|---------|---------|
| magenta/api | dev | REST API server |
| magenta/agent-ops | dev | Agent operations |
| magenta/agent-orchestrator | dev | Mission orchestration |
| magenta/mcp-bridge | dev | MCP gateway |
| magenta/mcp-web | dev | Web gateway |
| magenta/mcp-finops | dev | FinOps tools |
| magenta/collector | dev | Log collectors |
| magenta/worker | dev | Background workers |
| magenta/scheduler | dev | Task scheduler |

### Data Plane Images

| Image | Version | Purpose |
|-------|---------|---------|
| qdrant/qdrant | v1.12.0 | Vector database |
| ollama/ollama | 0.5.7 | LLM inference |
| redis | 7.4-alpine | Cache/state |
| elasticsearch | 8.12.0 | Search/registry |
| postgres | 16-alpine | SQL persistence |
| minio | latest | Object storage |

### Observability Images

| Image | Version | Purpose |
|-------|---------|---------|
| otel/opentelemetry-collector | 0.96.0 | Telemetry collection |
| prom/prometheus | v2.50.0 | Metrics |
| grafana/grafana | 10.3.1 | Dashboards |
| grafana/tempo | 2.4.0 | Distributed tracing |
| grafana/loki | 3.0.0 | Log aggregation |

---

## Network Configuration

### Port Map

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| API Server | 8000 | HTTP | REST API |
| MCP Bridge | 8080 | HTTP | MCP gateway |
| MCP Web | 8081 | HTTP | Web gateway |
| Agent Ops | 50060 | gRPC | Agent tools |
| Orchestrator | 50061 | gRPC | Mission control |
| FinOps | 50062 | HTTP | Cost tools |
| Qdrant REST | 6333 | HTTP | Vector DB |
| Qdrant gRPC | 6334 | gRPC | Vector DB |
| OLLAMA | 11434 | HTTP | LLM inference |
| Redis | 6379 | TCP | Cache |
| Elasticsearch | 9200 | HTTP | Search |
| PostgreSQL | 5432 | TCP | SQL |
| MinIO | 9000 | HTTP | Object store |
| Prometheus | 9090 | HTTP | Metrics |
| Grafana | 3000 | HTTP | Dashboards |

### Network Policies

```yaml
# Allow intra-namespace communication
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-intra-namespace
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector: {}
  egress:
    - to:
        - podSelector: {}
    - to:
        - namespaceSelector: {}
```

---

## Storage Requirements

### Persistent Volumes

| Component | Size | Access Mode | Storage Class |
|-----------|------|-------------|---------------|
| Qdrant | 50Gi | ReadWriteOnce | ssd |
| Elasticsearch | 100Gi | ReadWriteOnce | ssd |
| PostgreSQL | 50Gi | ReadWriteOnce | ssd |
| MinIO | 100Gi | ReadWriteOnce | standard |
| Prometheus | 50Gi | ReadWriteOnce | ssd |
| Redis | 5Gi | ReadWriteOnce | standard |
| OLLAMA | 20Gi | ReadWriteOnce | standard |

### Backup Strategy

| Component | Method | Frequency | Retention |
|-----------|--------|-----------|-----------|
| PostgreSQL | pg_dump + WAL archiving | Hourly | 30 days |
| Elasticsearch | Snapshot API | Daily | 90 days |
| Qdrant | Backup API | Daily | 30 days |
| Redis | RDB + AOF | Real-time | 7 days |
| MinIO | Versioning + replication | Real-time | 90 days |

---

## Security Hardening

### TLS Termination

- Ingress controller handles TLS termination
- Internal services communicate over mTLS (cert-manager)
- Certificates: Let's Encrypt (staging), External secrets operator

### RBAC Configuration

```yaml
# Service accounts per component
apiVersion: v1
kind: ServiceAccount
metadata:
  name: magenta-api
  namespace: magenta
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: magenta-api-role
  namespace: magenta
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list"]
```

### Secret Management

| Method | Purpose |
|--------|---------|
| External Secrets Operator | Cloud provider secrets |
| Sealed Secrets | GitOps-compatible secrets |
| Vault (optional) | Dynamic secrets, rotation |

### Pod Security

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault
containers:
  - securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
          - ALL
```

---

## Environment Variables

### Required Secrets

| Variable | Source | Purpose |
|----------|--------|---------|
| `MAGENTA_EVENTHUB__CONNECTION_STRING` | Secret | Event Hubs |
| `MAGENTA_ELASTIC__HOSTS` | ConfigMap | Elasticsearch |
| `MAGENTA_ELASTIC__USERNAME` | Secret | Elasticsearch auth |
| `MAGENTA_ELASTIC__PASSWORD` | Secret | Elasticsearch auth |
| `MAGENTA_SQL__URL` | Secret | PostgreSQL connection |
| `MAGENTA_AZURE_AUTH__TENANT_ID` | Secret | Azure AD |
| `MAGENTA_AZURE_AUTH__CLIENT_ID` | Secret | Azure AD |
| `MAGENTA_AZURE_AUTH__CLIENT_SECRET` | Secret | Azure AD |

### Required ConfigMaps

| Variable | Value | Purpose |
|----------|-------|---------|
| `MAGENTA_ENV` | staging/production | Environment |
| `MAGENTA_TELEMETRY__ENABLED` | true | Enable OTel |
| `MAGENTA_TELEMETRY__OTLP_ENDPOINT` | tempo:4317 | OTLP endpoint |
| `MAGENTA_GATEWAY__MODE` | shadow/enforcing | LLM gateway mode |
| `MESH__QDRANT_HOST` | qdrant | Vector DB host |
| `MESH__OLLAMA_HOST` | http://ollama:11434 | LLM endpoint |
| `MESH__REDIS_HOST` | redis | Cache host |

---

## Quick Start

### Local Development

```bash
# Start data mesh
docker compose -f data/deploy/docker-compose.yml up -d

# Start SOA services
docker compose -f soa/docker/docker-compose.minikube.yml up -d

# Verify health
curl http://localhost:8000/api/v1/health
curl http://localhost:8080/mcp/health
```

### Staging Deployment

```bash
# Apply base manifests
kubectl apply -k soa/kubernetes/base

# Apply staging overlay
kubectl apply -k soa/kubernetes/overlays/staging

# Verify deployment
kubectl get pods -n magenta
kubectl get svc -n magenta
```

### Production Deployment

```bash
# Apply production overlay
kubectl apply -k soa/kubernetes/overlays/production

# Verify with monitoring
kubectl get pods -n magenta -w
curl https://magenta-api.example.com/api/v1/health
```

---

## Validation Checklist

- [ ] All pods running and healthy
- [ ] Ingress configured with TLS
- [ ] Secrets mounted correctly
- [ ] Persistent volumes bound
- [ ] Network policies applied
- [ ] RBAC configured
- [ ] Monitoring dashboards accessible
- [ ] Alerts configured
- [ ] Backups scheduled
- [ ] Log aggregation working
- [ ] TLS certificates valid
- [ ] Rate limiting enabled
- [ ] CORS configured
- [ ] Health checks passing
- [ ] Readiness probes configured
- [ ] Resource limits set
- [ ] Pod disruption budgets configured
