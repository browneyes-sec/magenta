# Magenta ASOAR — Agent Context

## Project Identity

**Magenta** is an AI-driven Autonomous Security Operations and Response (ASOAR) platform. It orchestrates a swarm of security agents that plan, execute, and learn from security operations across SIEM, SOAR, threat intelligence, identity, and FinOps domains.

**The 5 pillars:**
| Pillar | Domain | MCP Service | Status |
|---|---|---|---|
| Sentinel | SIEM | `mcp-sentinel` (port 50051) | Defined in catalog |
| Entra ID | IAM | `mcp-entra-id` (port 50052) | Defined in catalog |
| Defender | EDR | `mcp-defender` (port 50053) | Defined in catalog |
| Threat Intel | TI | `mcp-threat-intel` (port 50054) | Defined in catalog |
| Agent Ops | Governance | `mcp-agent-ops` (port 50060) | Implemented |

---

## Repository Map

```
magenta/
├── magenta/agent_ops/       # Python MCP tool handlers (config, iac, cloud, finops)
├── magenta/mesh/            # Vectorized data mesh (memory, pipeline, BM25, lineage)
├── magenta/agents/          # Agent base classes (LLMAgent with retrieve_context)
├── magenta/core/            # Core models (AgentConfig, Mission, enums)
├── soa/                     # Service-Oriented Architecture layer
│   ├── config/              # TOML configs + JSON Schema validation
│   ├── terraform/           # Multi-cloud IaC (AKS, EKS, GKE, vSphere, network, budget)
│   ├── kubernetes/          # K8s manifests + kustomize overlays (base/dev/staging/prod)
│   ├── docker/              # Dockerfiles + docker-compose files
│   ├── services/            # MCP service TOML definitions + catalog
│   ├── proto/               # gRPC protobuf definitions
│   └── monitoring/          # Grafana dashboards
├── scripts/mesh/            # Operational validation tools
│   ├── validate_memory.py   # Memory health checks
│   ├── rag_accuracy.py      # RAG accuracy measurement (NDCG@5)
│   └── seed_eval_data.py    # Seed eval data for accuracy testing
├── tests/eval/              # Golden dataset for RAG evaluation
├── architecture/            # System architecture docs + ADRs (18 records)
├── data/                    # Data mesh: Qdrant + OLLAMA + Redis + MinIO + mesh gateway
├── docs/                    # User guides, deployment docs, usage guides
├── context/                 # Per-domain CLAUDE.md files for agent personas
├── .ai/                     # AI integration docs (MCP, A2A, ADK, agents)
├── .github/                 # CI workflows + actions
└── AGENTS.md                # ← You are here
```

---

## Architecture Invariants

These rules must not be violated without a new ADR:

1. **Cost split**: Azure 65%, AWS 25%, vSphere 10% — enforced by `multicloud.toml` and budget module.
2. **MCP-first**: All agent-to-service communication goes through the MCP Bridge (`mcp-bridge:8080`). No direct service calls.
3. **TOML config**: All configuration is TOML, validated against JSON Schema. No YAML for app config (HCL is ok for Terraform).
4. **Kustomize 3-tier**: K8s deployments use `base/` → `overlays/{dev,staging,prod}/`. No Helm charts.
5. **Terraform CLI**: IaC tools use `terraform` binary via subprocess, not python bindings.
6. **Per-provider modules**: AKS, EKS, GKE, vSphere each have dedicated Terraform modules (not monolithic conditionals).

---

## Common Patterns

### Adding a new MCP tool
1. Add handler function in `magenta/agent_ops/<domain>.py`
2. Register in `TOOLS` dict in `server.py`
3. Add RPC in `soa/proto/agent_ops.proto`
4. Add tool definition in `soa/services/agent-ops-service.toml`

### Adding a new cloud provider
1. Add provider class in `magenta/agent_ops/cloud.py` (implementing dispatch interface)
2. Add Terraform module in `soa/terraform/modules/<provider>/`
3. Register in `soa/config/providers.toml`
4. Add feature flag in `soa/terraform/variables.tf`

### Adding a new K8s service
1. Write Deployment + Service + SA + RBAC manifest in `soa/kubernetes/`
2. Add to `soa/kubernetes/base/kustomization.yaml`
3. Create any necessary overlay patches

### Adding a new Terraform module
1. Create module dir under `soa/terraform/modules/<name>/` with `main.tf`, `variables.tf`, `outputs.tf`
2. Wire into root `soa/terraform/main.tf` with a feature flag
3. Add root variables in `soa/terraform/variables.tf`
4. Add to staging/production `terraform.tfvars`

### Config validation flow
```
File change in soa/config/ → PR → CI (config_validate) → 
  JSON Schema check → secret scan → deprecation check → 
  merge → configMap update → pod restart
```

---

## Naming Conventions

| Resource | Pattern | Example |
|---|---|---|
| MCP service IDs | `mcp-{domain}` | `mcp-agent-ops`, `mcp-finops`, `mcp-web` |
| Agent deployments | `{agent-type}` | `agent-ops`, `agent-orchestrator` |
| K8s namespaces | `magenta-{layer}` | `magenta-soa`, `magenta-agents`, `magenta-finops` |
| Terraform modules | `{provider}` | `aks`, `eks`, `gke`, `vsphere`, `network`, `budget` |
| Terraform resources | `magenta-{env}-{type}` | `magenta-staging-aks`, `magenta-prod-hub-vnet` |
| Docker images | `magenta/{service}:{tag}` | `magenta/agent-ops:0.1.0` |
| Branches | `feature/{slug}` or `fix/{slug}` | `feature/agent-memory`, `fix/budget-overflow` |
| Config files | `{domain}.toml` | `providers.toml`, `finops.toml`, `agents.toml` |
| Schema files | `{domain}.schema.json` | `providers.schema.json`, `finops.schema.json` |

---

## Port & Namespace Quick-Ref

| Service | Port | Protocol | Namespace | Health Check |
|---|---|---|---|---|
| MCP Bridge | 8080 | HTTP | `magenta-soa` | `/mcp/health` |
| MCP Web | 8081 | HTTP | `magenta-soa` | `/mcp/web/health` |
| Agent Ops | 50060 | gRPC | `magenta-agents` | `/mcp/agent-ops/health` |
| Agent Orchestrator | 50061 | gRPC | `magenta-agents` | `/mcp/orchestrator/health` |
| MCP FinOps | 50062 | HTTP | `magenta-finops` | `/mcp/finops/health` |
| Mesh Gateway | 8000 | HTTP | `magenta-mesh` | `/api/v1/mesh/health` |
| Qdrant | 6333/6334 | REST/gRPC | `magenta-mesh` | `/healthz` |
| OLLAMA | 11434 | HTTP | `magenta-mesh` | `/api/health` |
| Redis | 6379 | TCP | `magenta-mesh` | `PING` |
| MinIO | 9000 | HTTP | `magenta-mesh` | `/minio/health/live` |

All services expose metrics on port 9090.

---

## Workflow Shortcuts

### Local dev
```bash
make dev           # docker compose up all SOA services
make dev-mesh      # docker compose up data mesh (Qdrant + OLLAMA + Redis)
make test          # run Python tests with pytest
make lint          # terraform fmt + markdownlint + ruff + yamllint
```

### Memory operations (ADR-018)
```bash
python scripts/mesh/validate_memory.py --env dev --verbose    # health check
python scripts/mesh/validate_memory.py --env dev --write-test # round-trip test
python scripts/mesh/seed_eval_data.py --env dev --clear-first # seed eval data
python scripts/mesh/rag_accuracy.py --env dev --verbose       # NDCG@5 measurement
python scripts/mesh/setup_collections.py --env dev --indexes  # create Qdrant collections
python scripts/mesh/pull_models.py --env dev --verify         # pull OLLAMA models
```

### Terraform
```bash
make tf-init       # terraform init -backend=false
make tf-plan       # terraform plan (staging)
make tf-apply      # terraform apply (staging, requires approval)
```

### K8s
```bash
make k8s-dev       # kubectl apply -k soa/kubernetes/overlays/dev
make k8s-staging   # kubectl apply -k soa/kubernetes/overlays/staging
make k8s-prod      # kubectl apply -k soa/kubernetes/overlays/production
```

---

## Commit Convention

All commits must follow **Conventional Commits**:

```
<type>(<scope>): <description>

[optional body]
```

Types: `feat`, `fix`, `docs`, `infra`, `refactor`, `test`, `chore`
Scopes: `agent-ops`, `terraform`, `k8s`, `config`, `finops`, `docs`, `ci`

Examples:
```
feat(agent-ops): add finops_forecast tool with Prophet backend
fix(terraform): correct AKS subnet_id variable type
docs(adr): add ADR-008 for CI FinOps gates
infra(ci): add drift detection schedule to terraform-ci.yml
```

---

## ADR Index

| # | Title | Status |
|---|---|---|
| 001 | Multi-Cloud Provider Strategy | Accepted |
| 002 | MCP as Service Integration Protocol | Accepted |
| 003 | TOML as Configuration Plane | Accepted |
| 004 | Terraform CLI Subprocess Pattern | Accepted |
| 005 | Per-Provider K8s Module Decomposition | Accepted |
| 006 | Kustomize Overlay Structure | Accepted |
| 007 | Agent Ops Tool Registry Pattern | Accepted |
| 008 | CI/FinOps Gates as SDLC Enforcers | Accepted |
| 009 | Hub-and-Spoke Multi-Cloud Networking | Accepted |
| 010 | Vectorized Data Mesh Architecture | Accepted |
| 011 | Telemetry Collection Plane | Accepted |
| 012 | Parallel DAG Execution | Accepted |
| 013 | Sync Fallback Path | Accepted |
| 014 | Mesh Memory Integration | Accepted |
| 015 | Minimum Viable Subset | Accepted |
| 016 | Golden Image Strategy | Accepted |
| 017 | Open WebUI Operator Control Plane | Accepted |
| 018 | LLM-RAG Hybrid Memory Architecture | Accepted |
