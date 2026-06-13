# Magenta SOA — Service-Oriented Architecture for MCP

**Version:** 1.0
**Layer:** Service encapsulation, container orchestration, multi-cloud IaC, FinOps

---

## Architecture

Magenta SOA wraps every API resource and microservice into **MCP (Model Context Protocol) services** — containerized, deployable units that agents discover and invoke through a unified protocol. The SOA layer manages service lifecycle, multi-cloud provisioning, cost governance, and configuration across public, private, hybrid, and multicloud topologies.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      AGENT OPERATIONS SUITE                              │
│                                                                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────────┐  │
│  │ Triage Agent │ │ Containment  │ │ Enrich Agent │ │ Agent Ops     │  │
│  │              │ │ Agent        │ │              │ │ (Config, IaC, │  │
│  │              │ │              │ │              │ │  FinOps)      │  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └───────┬───────┘  │
│         │                │                │                 │          │
│         ▼                ▼                ▼                 ▼          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                   MCP PROTOCOL BRIDGE                               │  │
│  │  Universal tool gateway: discovery, auth, routing, rate-limiting   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│         │                │                │                 │          │
│         ▼                ▼                ▼                 ▼          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    SERVICE MESH (K8s)                               │  │
│  │                                                                      │  │
│  │  mcp-sentinel ── mcp-entra-id ── mcp-defender ── mcp-data-mesh     │  │
│  │  mcp-servicenow ── mcp-threat-intel ── mcp-agent-ops ── mcp-bridge│  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                               │                                         │
├───────────────────────────────┼─────────────────────────────────────────┤
│  ┌────────────────────────────▼──────────────────────────────────────┐  │
│  │               INFRASTRUCTURE AS CODE (Terraform)                   │  │
│  │                                                                     │  │
│  │  Azure ─── AWS ─── GCP ─── Private Cloud ─── Hybrid/Multicloud     │  │
│  │  Compute · Storage · Network · K8s · Identity · Cost               │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Principles

| Principle | Implementation |
|---|---|
| **MCP-first** | Every service exposes MCP for agent consumption; no raw API calls |
| **Container-native** | All services run as containers (Docker → K8s); no bare-metal agents |
| **Config as TOML** | Human-readable system configuration in TOML with JSON Schema validation |
| **Provider-agnostic IaC** | Terraform modules for Azure, AWS, GCP, private cloud with unified variables |
| **FinOps by default** | Every resource has cost tags, budgets, and optimization policies |
| **Agent-managed ops** | Agent Ops manages config, IaC, resource provisioning, and cost analysis |

## Directory Structure

```
soa/
├── readme.md                        ← This file
├── services/                        ← MCP service definitions (TOML)
│   ├── catalog.toml                 ← Full service registry
│   ├── mesh-service.toml            ← Data mesh MCP wrapper
│   ├── agent-ops-service.toml       ← Config + IaC + FinOps agent MCP
│   └── finops-service.toml          ← FinOps cost analysis MCP
├── docker/                          ← Container definitions
│   ├── Dockerfile.mcp-bridge        ← MCP protocol bridge
│   ├── Dockerfile.agent-ops         ← Agent Ops runtime
│   └── Dockerfile.agent-orchestrator ← Swarm orchestrator runtime
├── terraform/                       ← Multi-cloud IaC
│   ├── main.tf                      ← Root module
│   ├── providers.tf                 ← Azure + AWS + GCP + vSphere
│   ├── modules/
│   │   ├── compute/                 ← VM, AKS, EKS, GKE resources
│   │   └── kubernetes/             ← K8s cluster provisioning
│   ├── environments/
│   │   └── dev/                     ← Dev environment tfvars
│   └── README.md
├── kubernetes/                      ← Service mesh manifests
│   ├── minikube/                    ← Local dev with minikube
│   ├── namespaces/                  ← Multi-tenant namespaces
│   ├── mcp-services/                ← MCP service deployments
│   ├── agents/                      ← Agent runtime deployments
│   └── kustomization.yaml           ← Top-level kustomize
├── config/                          ← TOML system configuration
│   ├── system.toml                  ← Global system settings
│   ├── providers.toml               ← Cloud provider definitions
│   ├── agents.toml                  ← Agent role config
│   ├── finops.toml                  ← Cost governance rules
│   └── multicloud.toml              ← Multi-cloud topology
└── pyproject.toml                   ← Python project for MCP agents
```

## Agent Ops — Configuration & Infrastructure Agent

The **Agent Ops** service is an MCP-wrapped agent that owns:

- **Configuration analysis** — validates, audits, and reconciles TOML/YAML/JSON configs across the mesh
- **IaC management** — plans and applies Terraform changes, drift detection, state management
- **Multi-cloud orchestration** — provisions resources across Azure, AWS, GCP, private cloud from unified specs
- **FinOps** — monitors compute/storage consumption, recommends right-sizing, enforces budgets

See [`services/agent-ops-service.toml`](services/agent-ops-service.toml) for full tool catalog.

## Quickstart

```bash
# 1. Start local minikube cluster
./kubernetes/minikube/start.sh

# 2. Deploy SOA namespace and MCP bridge
kubectl apply -k kubernetes/

# 3. Verify MCP services
kubectl -n magenta-soa get mcp-services
curl -X POST http://localhost:8080/mcp/discover

# 4. Query Agent Ops for configuration health
mcp call agent-ops.analyze_config --config-dir config/

# 5. Plan infrastructure
mcp call agent-ops.plan_infrastructure --environment dev
```
