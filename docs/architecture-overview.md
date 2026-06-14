# Architecture Overview

## System Context

Magenta ASOAR is a multi-cloud security orchestration platform that combines a vectorized data mesh with an MCP-based service mesh. Agents use MCP tools to manage infrastructure, analyze costs, and orchestrate security workflows across Azure (65%), AWS (25%), and vSphere (10%).

```
┌─────────────────────────────────────────────────────────┐
│                     MCP Bridge (8080)                    │
│         HTTP Gateway — routes tool requests              │
└──────┬──────────┬──────────┬──────────┬─────────────────┘
       │          │          │          │
       ▼          ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│ Agent    │ │ Agent    │ │ Web      │ │ FinOps       │
│ Ops      │ │ Orch.    │ │ Gateway  │ │ MCP          │
│ :50060   │ │ :50061   │ │ :8081    │ │ :50062       │
│ (gRPC)   │ │ (gRPC)   │ │ (HTTP)   │ │ (gRPC)       │
└────┬─────┘ └──────────┘ └────┬─────┘ └──────┬───────┘
     │                          │               │
     ▼                          ▼               ▼
┌──────────────────────────────────────────────────────┐
│                 Terraform Multi-Cloud IaC             │
│  AKS (Azure) │ EKS (AWS) │ GKE (GCP) │ vSphere (IL5) │
│  Network Hub │ Budgets │ Cost Monitoring              │
└──────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│              Vectorized Data Mesh                      │
│  Qdrant (vectors) │ OLLAMA (embeddings) │ Redis (cache)│
│  MinIO (objects) │ Debezium (CDC)                      │
└────────────────────────────────────────────────────────┘
```

## Architecture Decisions

All architectural decisions are recorded as MADR-format ADRs in `architecture/ADR/`:

| # | Decision | Status |
|---|---|---|
| 001 | Multi-Cloud Strategy (Azure 65%, AWS 25%, vSphere 10%) | Accepted |
| 002 | MCP Protocol for Service Integration | Accepted |
| 003 | TOML for Configuration Plane | Accepted |
| 004 | Terraform CLI via Subprocess (not python-terraform) | Accepted |
| 005 | Per-Provider K8s Modules over Monolithic Compute | Accepted |
| 006 | Kustomize Overlays over Helm | Accepted |
| 007 | Agent-Ops Tool Registry with gRPC | Accepted |
| 008 | CI/FinOps Gates (Infracost, tag compliance, drift) | Accepted |
| 009 | Hub-and-Spoke Multi-Cloud Networking | Accepted |
| 010 | Vectorized Data Mesh for Agent Memory | Accepted |

## Service Catalog

Services are defined in `soa/services/catalog.toml`:

| Service | Port | Protocol | Namespace | Description |
|---|---|---|---|---|
| mcp-bridge | 8080 | HTTP | magenta-soa | MCP routing gateway |
| agent-ops | 50060 | gRPC | magenta-agents | Terraform, cloud, FinOps tools |
| agent-orchestrator | 50061 | gRPC | magenta-agents | Agent lifecycle management |
| mcp-web | 8081 | HTTP | magenta-soa | REST API integration |
| mcp-finops | 50062 | gRPC | magenta-finops | Cost analysis and budgets |

## Namespaces

| Namespace | Purpose | Services |
|---|---|---|
| magenta-soa | Core SOA services | mcp-bridge, mcp-web |
| magenta-agents | Agent runtime | agent-ops, agent-orchestrator |
| magenta-mesh | Data mesh | mesh-gateway |
| magenta-finops | Cost management | mcp-finops, OpenCost |
| magenta-observability | Monitoring | Prometheus, Grafana (future) |

## Data Flow

1. **Agent → MCP Bridge**: An agent sends an MCP tool request (HTTP POST to `/rpc`).
2. **MCP Bridge → Backend**: The bridge routes the request to the appropriate backend service based on the tool name prefix (`config_*` → agent-ops, `iac_*` → agent-ops, `finops_*` → mcp-finops, etc.).
3. **Backend → Cloud**: The backend service executes the operation — Terraform subprocess, cloud SDK call, or vector query — and returns the result.
4. **Response → Agent**: The result flows back through MCP Bridge to the agent, with memory optionally persisted to the data mesh.

## Infrastructure Layers

```
┌─────────────────────────────────────────────────────────┐
│                   CI/CD (GitHub Actions)                 │
│  terraform-ci.yml │ finops-gate.yml │ Infracost │ Drift │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                  Kubernetes (AKS / EKS)                  │
│  magent-services │ magent-agents │ magent-finops │ ...  │
│  Kustomize overlays: base → dev → staging → production  │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                  Terraform Multi-Cloud                   │
│  Azure (AKS, VNet, Budget) │ AWS (EKS, TGW) │ GCP (GKE) │
│  vSphere (VM template, IL5 isolation)                    │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                  Data Mesh (Docker / K8s)                │
│  Qdrant / OLLAMA / Redis / MinIO / Debezium / Gateway   │
└─────────────────────────────────────────────────────────┘
```

## Deployment Environments

| Environment | Cluster | Terraform State | Image Tag | Purpose |
|---|---|---|---|---|
| dev | Minikube (local) | Local | `:dev` | Local development |
| staging | AKS (dev-test) | Azure Storage `stage` | `:staging` | Integration testing |
| production | AKS + EKS | Azure Storage `prod` | semver tag | Production workloads |
