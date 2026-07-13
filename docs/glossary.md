# Glossary

## A

- **ADR (Architecture Decision Record)** — A MADR-format document that captures a significant architectural decision, its context, options considered, and rationale. Stored in `architecture/ADR/ADR-{NNN}-{slug}.md`.
- **Agent** — An autonomous AI entity executing tasks via MCP tools. Agents have episodic, semantic, and procedural memory stored in the vector data mesh.
- **Agent Ops** — The MCP service (`agent-ops-service`) that provides Terraform, cloud provisioning, FinOps, and configuration tools to agents. Runs on port 50060 (gRPC).
- **ASOAR** — Automated Security Orchestration, Automation, and Response — the domain of this project.
- **AZ CLI** — Azure Command-Line Interface, used by the cloud provisioning tools.

## B

- **Budget module** — A Terraform module (`soa/terraform/modules/budget/`) that creates Azure subscription budgets and provider-specific budgets with tiered notification alerts (50/80/95%).

## C

- **CDC (Change Data Capture)** — A technique used by Debezium to capture row-level changes from SQL and NoSQL databases for streaming into the vector data mesh.
- **Conventional Commits** — A commit message convention (`<type>(<scope>): <description>`) enforced by the project. Types: `feat`, `fix`, `docs`, `infra`, `refactor`, `test`, `chore`.
- **Cost analysis** — A FinOps tool that queries Azure Cost Management and AWS Cost Explorer APIs for multi-cloud cost reporting.

## D

- **Data mesh** — An architectural paradigm for the vectorization pipeline: ingests data from external databases via CDC (Debezium), embeddings (OLLAMA), stores vectors (Qdrant), and exposes a federated query API.
- **Drift detection** — A Terraform `plan -detailed-exitcode` comparison against the last committed state to detect infrastructure drift. Run weekly by `terraform-ci.yml`.

## E

- **Episodic memory** — Agent memory type storing discrete interaction events (tool calls, results). Stored in Qdrant with temporal metadata.

## F

- **FinOps** — Financial Operations — cloud cost management practices. In Magenta, this includes budget enforcement, tag compliance, right-sizing recommendations, and cost forecasting.

## G

- **gRPC** — The transport protocol for Agent Ops tool invocations. Defined in `soa/proto/agent_ops.proto`.

## H

- **Hub-and-spoke network** — A network topology where a central Azure VNet (hub) connects to spoke VNets in Azure, AWS (via Transit Gateway), and GCP (via VPC peering). Defined in `soa/terraform/modules/network/`.

## I

- **Infracost** — A cost estimation tool for Terraform. Runs in CI (informational) on every PR with `environment/terraform-ci.yml`. Produces cost diffs visible as PR comments.
- **IL5** — Impact Level 5 — a US DOD security classification for controlled unclassified information (CUI). vSphere workloads handling IL5 data run in network-isolated private cloud.

## K

- **Kustomize** — A Kubernetes configuration customization tool. Magenta uses 3-tier overlays: `base/` + `overlays/{dev,staging,production}/`.

## M

- **MCP (Model Context Protocol)** — The universal service integration protocol used by Magenta. Version `2025-03-26` across all services. MCP Bridge on port 8080 routes tool requests to backend services.
- **MCP Bridge** — The HTTP gateway (`soa/docker/Dockerfile.mcp-bridge`) that routes MCP tool requests to the appropriate backend service. Entry point for all agent-to-service communication.
- **Mesh Gateway** — The HTTP/gRPC gateway for the data mesh. Exposes the unified query endpoint on port 8000.

## O

- **OLLAMA** — Local LLM serving engine used for generating embeddings (`nomic-embed-text` model) in the vectorization pipeline.
- **OpenCost** — A Kubernetes cost monitoring tool deployed in `magenta-finops` namespace. Exposes Prometheus metrics for the Grafana cost dashboard.

## P

- **Procedural memory** — Agent memory type storing learned workflows and action sequences. Encoded as structured procedure graphs in Qdrant.

## Q

- **Qdrant** — The vector database used for storing agent memories and indexed embeddings. Runs as a StatefulSet with PVC.

## R

- **Right-sizing recommendation** — A FinOps tool that analyzes CPU/memory utilization and generates instance/sku downsize or upgrade suggestions.
- **Ruff** — A fast Python linter and formatter used in `pre-commit` and CI.

## S

- **Semantic memory** — Agent memory type storing factual knowledge (context, domain concepts, learned facts). Indexed via embeddings in Qdrant.
- **SOA (Service-Oriented Architecture)** — The architectural style organizing Magenta into discrete MCP services with TOML service catalog and catalog-based discovery.

## T

- **Tag compliance** — A CI gate that checks Azure and AWS resources for mandatory tags (`environment`, `cost-center`, `owner`, `project`, `data-classification`). Hard block if >5 resources are non-compliant.
- **TOML** — Human-readable configuration format used for service definitions, mesh settings, and tool configurations. Validated by JSON Schema in CI.

## U

- **uv** — Python package manager and resolver used by Magenta. Replaces pip/poetry. Lockfile: `uv.lock`.

## V

- **Vector embedding** — A numerical representation of data generated by OLLAMA (`nomic-embed-text`). Used for semantic search and agent memory retrieval.
- **vSphere** — VMware virtualization platform used for IL5 private cloud workloads (10% allocation).

## W

- **Workload Identity** — Azure AD OIDC federation for authenticating Terraform and K8s workloads without static credentials.
