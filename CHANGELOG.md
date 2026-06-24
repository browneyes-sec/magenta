# Changelog

All notable changes to Magenta ASOAR are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Agent Ops (Sprint 1)
- `magenta/agent_ops/` package with 6 files (~800 lines): MCP server, tool registry, 14 tool handlers
- Configuration analysis: `config_analyze`, `config_validate`, `config_diff` with TOML/YAML/JSON/HCL parsers, JSON Schema validation, secret scanning, deprecation detection, best-practice checks
- IaC management: `iac_plan`, `iac_apply`, `iac_drift_detect` via Terraform CLI subprocess with `-detailed-exitcode` drift
- Multi-cloud orchestration: `cloud_provision`, `cloud_discover`, `cloud_migrate` with Azure/AWS/GCP/vSphere SDK dispatch
- FinOps: `finops_cost_analysis` (Azure CM + AWS CE), `finops_recommend_rightsize` (CPU metrics), `finops_forecast` (Prophet), `finops_enforce_budget`, `finops_tag_compliance`
- gRPC proto definition: `soa/proto/agent_ops.proto` — 15 RPCs matching the tool catalog
- JSON Schema files: 5 schemas for system, providers, agents, finops, multicloud configs
- Web service TOML: `soa/services/web-service.toml` — HTTP MCP wrapper for the REST API layer

#### Terraform Modules (Sprint 2)
- `soa/terraform/modules/aks/` — AKS with AAD RBAC, private cluster, user node pools, container insights
- `soa/terraform/modules/eks/` — EKS with IRSA/OIDC, managed node groups, VPC CNI addons, audit logging
- `soa/terraform/modules/gke/` — GKE with workload identity, VPC-native, shielded nodes, release channels
- `soa/terraform/modules/vsphere/` — VM template cloning, static IP assignment, control-plane/worker split
- `soa/terraform/modules/network/` — Hub-and-spoke: Azure VNet peering, AWS Transit Gateway, GCP VPC
- `soa/terraform/variables.tf` — Consolidated root variable catalog (65 vars)
- `soa/terraform/outputs.tf` — Consolidated root outputs
- Staging environment: `environments/staging/backend.tf + terraform.tfvars`
- Production environment: `environments/production/backend.tf + terraform.tfvars`
- Dual-path module migration: `use_new_k8s_modules` flag for backward-compatible rollout

#### Kubernetes & Docker (Sprint 3)
- `mcp-finops.yaml` — FinOps service: Deployment, Service, SA, ClusterRole (port 50062, namespace `magenta-finops`)
- `mcp-web.yaml` — Web API proxy: Deployment, Service, SA, Role (port 8081, upstream `magenta-api:8000`)
- `agent-orchestrator.yaml` — Swarm orchestrator: Deployment, Service, SA, PVC, ClusterRole (port 50061)
- Kustomize 3-tier overlays: `base/` + `overlays/{dev,staging,production}/` with environment-specific replicas, resources, image tags
- `Dockerfile.web-gateway` — Multi-stage Python/uvicorn for the web MCP gateway
- `docker-compose.minikube.yml` — 5-service local dev stack (mcp-bridge, agent-ops, agent-orchestrator, mcp-web, mcp-finops)

#### CI & FinOps Gates (Sprint 4)
- `terraform-ci.yml` — 4 jobs: validate, plan (matrix x3 envs), Infracost (PR cost comment), drift detection (weekly cron)
- `finops-gate.yml` — 3 jobs: tag compliance (Azure graph + AWS tagging), budget check (Azure consumption), cost report (Slack)
- `infracost-setup` — Composite GitHub Action for Infracost install
- Grafana dashboard: `soa/monitoring/grafana/dashboards/cost-overview.json` — 7 panels (MTD, budget gauge, trend, provider pie, env bar, top-10 table, 30d forecast)
- Azure Budget module: `soa/terraform/modules/budget/` — subscription + per-provider budgets with 3-tier notifications and Slack webhook
- Budget variables wired into root `main.tf`, `variables.tf`, `outputs.tf`, and both environment tfvars

#### Architecture & SDLC
- 10 ADRs in `architecture/ADR/ADR-001` through `ADR-010`
- `AGENTS.md` — Root context file for AI agents and human contributors
- `CONTRIBUTING.md` — Branch strategy, Conventional Commits, PR workflow, code style
- `DEVELOPMENT.md` — Local dev setup, testing, Terraform, K8s, CI/CD, troubleshooting
- `SECURITY.md` — Vulnerability reporting, auth, secrets management, supply chain, incident response
- `CHANGELOG.md` — This file
- `Makefile` — Common commands (dev, test, lint, build, deploy, clean, setup)
- `.editorconfig` — Editor consistency (2-space YAML/TOML/JSON/HCL, 4-space Python)
- `.pre-commit-config.yaml` — Git hooks (trailing whitespace, YAML/JSON/Terraform validation, markdownlint, hadolint, ruff)
- `.markdownlint.json` — Markdown linting rules (120 char, relaxed HTML)
- `.yamllint.yml` — YAML linting rules
- `scripts/setup-dev.sh` — One-command dev environment bootstrap
- GitHub templates: issue templates (bug, feature), PR template, CODEOWNERS, Dependabot config
- `docs/glossary.md` — Domain terminology reference

### Changed

- **Refactored** `soa/terraform/main.tf`: added network hub, per-provider K8s modules, vSphere cluster, budget module alongside legacy compute/kubernetes modules
- **Refactored** `soa/terraform/providers.tf`: extracted all variable blocks into `variables.tf`, keeping only provider configurations
- **Updated** `soa/kubernetes/kustomization.yaml`: added mcp-finops, mcp-web, agent-orchestrator resources and image configs

### Infrastructure

- Branch: `staging` SHA `6c292f0` — all Sprint 1-4 changes committed
