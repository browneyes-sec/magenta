# Development Setup

This guide covers setting up a local Magenta development environment.

## Prerequisites

| Tool | Version | Required For |
|---|---|---|
| Python | >= 3.12 | Agent Ops, mesh gateway, tooling |
| [uv](https://docs.astral.sh/uv/) | >= 0.5 | Python dependency management |
| Docker | >= 24 | Local service containers |
| Docker Compose | >= 2.24 | Multi-service orchestration |
| Terraform | >= 1.8 | IaC validation (optional for dev) |
| kubectl | >= 1.30 | K8s manifest validation (optional) |
| [minikube](https://minikube.sigs.k8s.io/) | >= 1.34 | Local K8s cluster (optional) |

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/browneyes-sec/magenta.git
cd magenta

# 2. Run the setup script
make setup

# 3. Start SOA services
make dev

# 4. Start data mesh (separate terminal)
make dev-mesh

# 5. Verify
curl http://localhost:8080/mcp/health          # MCP Bridge
curl http://localhost:50060/mcp/agent-ops/health  # Agent Ops
curl http://localhost:8000/api/v1/mesh/health  # Mesh Gateway
```

## Project Dependencies

### Python
The project uses `uv` for dependency management:

```bash
uv sync                          # Install all dependencies
uv sync --group dev              # Include dev dependencies (testing, linting)
uv sync --group finops           # Include FinOps extras (Prophet)
uv lock                          # Update lockfile after adding dependencies
```

### Docker
SOA services are built and run via Docker Compose:

```bash
make dev                         # Build and start all SOA services
make dev-mesh                    # Build and start data mesh services
make dev-logs                    # Tail all logs (ctrl+c to stop)
make dev-stop                    # Stop all services
```

## Testing

```bash
make test                        # Run all tests
make test-unit                   # Unit tests only (no external deps)
make test-integration            # Integration tests (requires Docker services)
make test-coverage               # Test with coverage report
```

Tests live in `magnet/` and mirror the `magenta/` package structure.

## Terraform

```bash
make tf-init                     # terraform init -backend=false
make tf-fmt                      # terraform fmt check
make tf-validate                 # terraform validate
make tf-plan-staging             # plan for staging environment
make tf-plan-prod                # plan for production environment
```

Terraform state is stored in Azure Storage (not local). For local validation, use `-backend=false`.

## Kubernetes

```bash
# Minikube (optional)
minikube start --profile magenta --cpus 4 --memory 8192

# Deploy SOA layer
kubectl apply -k soa/kubernetes/overlays/dev

# Verify
kubectl -n magenta-soa get pods
kubectl -n magenta-agents get pods
kubectl -n magenta-finops get pods
```

For a full minikube setup, see `soa/kubernetes/minikube/start.sh`.

## CI/CD

GitHub Actions workflows are in `.github/workflows/`:

- `terraform-ci.yml`: validates Terraform on every PR, runs Infracost, checks drift weekly.
- `finops-gate.yml`: checks tag compliance on PRs, reports budget status daily.

These require the following GitHub secrets:

| Secret | Source | Used By |
|---|---|---|
| `AZURE_CLIENT_ID` | Azure AD App Registration | finops-gate, drift detection |
| `AZURE_TENANT_ID` | Azure AD tenant | finops-gate, drift detection |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription | finops-gate, drift detection |
| `AWS_ACCESS_KEY_ID` | AWS IAM user | finops-gate |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM user | finops-gate |
| `SLACK_FINOPS_WEBHOOK` | Slack app webhook | finops-gate (optional) |

## Environment Variables

Key environment variables for local development:

```bash
# Agent Ops
AGENT_OPS__CONFIG_DIR=/app/config
AGENT_OPS__TERRAFORM_DIR=/app/terraform
AGENT_OPS__CLOUD_PROVIDERS=azure,aws,gcp
AGENT_OPS__FINOPS_ENABLED=true
AGENT_OPS__LOG_LEVEL=DEBUG

# MCP Bridge
MCP__AUTH_ENABLED=false          # Disable auth for local dev
MCP__RATE_LIMIT_PER_AGENT=200
MCP__LOG_LEVEL=DEBUG
```

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| `uv sync` fails | Python version mismatch | Run `python3 --version`, ensure >= 3.12 |
| Docker build fails | Architecture mismatch | Use `DOCKER_DEFAULT_PLATFORM=linux/amd64` |
| `terraform init` fails | No Azure backend | Add `-backend=false` flag |
| Minikube won't start | Resource contention | Reduce `--cpus` or `--memory` |
| MCP Bridge health fails | Config mount missing | Ensure `soa/config/` exists with all TOML files |
