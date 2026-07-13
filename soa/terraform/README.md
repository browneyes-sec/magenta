# Magenta — Terraform Multi-Cloud IaC

Multi-cloud infrastructure provisioning for the Magenta ASOAR platform.

## Directory Structure

```
terraform/
├── main.tf                        # Root module — orchestrates all providers + modules
├── providers.tf                   # Cloud provider configurations (Azure, AWS, GCP, vSphere)
├── variables.tf                   # Consolidated root variable catalog (65 vars)
├── outputs.tf                     # Consolidated root outputs
├── modules/
│   ├── compute/                   # Legacy monolithic compute module (deprecated)
│   ├── kubernetes/                # Legacy monolithic K8s module (deprecated)
│   ├── aks/                       # Azure AKS — AD RBAC, private cluster, node pools
│   ├── eks/                       # AWS EKS — IRSA/OIDC, managed node groups, VPC CNI
│   ├── gke/                       # GCP GKE — Workload Identity, VPC-native, shielded nodes
│   ├── vsphere/                   # vSphere — VM templates, static IP, IL5 isolation
│   ├── network/                   # Hub-and-spoke networking (Azure VNet, AWS TGW, GCP VPC)
│   └── budget/                    # Azure budget + provider-scoped budgets with Slack alerts
└── environments/
    ├── staging/
    │   ├── backend.tf             # Remote state in Azure Storage (stage container)
    │   └── terraform.tfvars       # Staging-specific values
    └── production/
        ├── backend.tf             # Remote state in Azure Storage (prod container)
        └── terraform.tfvars       # Production-specific values
```

## Module Migration

The root `main.tf` supports dual-path module selection via `use_new_k8s_modules`:

| Flag | Legacy Path | New Path |
|---|---|---|
| `false` (default) | `compute/` + `kubernetes/` | — |
| `true` | — | `aks/`, `eks/`, `gke/`, `vsphere/`, `network/` |

This allows zero-downtime migration from the monolithic modules to per-provider modules.

## Environments

| Environment | State Backend | Purpose |
|---|---|---|
| `staging` | Azure Storage (account: `magentaterraform`) | Integration testing, CI validation |
| `production` | Azure Storage (account: `magentaterraform`) | Production workloads on AKS + EKS |

## Usage

```bash
# Init — backend-free for local validation
make tf-init

# Validate
make tf-validate

# Plan (staging)
make tf-plan-staging

# Plan (production)
make tf-plan-prod

# Apply via Agent Ops or directly
terraform apply -var-file=environments/staging/terraform.tfvars

# Drift detection via Agent Ops
mcp call agent-ops.iac_drift_detect --environment staging
```

## Budget & Cost Governance

The `budget` module creates:
- **Subscription-level budget**: 50/80/95% alerts to Slack
- **Provider-scoped budgets**: Per-provider cost limits managed via `provider_budgets` variable

Every resource must be tagged with:
- `cost-center` — maps to budget owner
- `environment` — dev/staging/production
- `project` — aggregates all magenta resources
- `owner` — team or individual responsible
- `data-classification` — public/internal/confidential/il5

Agent Ops `finops_tag_compliance` validates these tags across all providers.

## Adding a New Provider Module

1. Create `modules/<provider>/` with `main.tf`, `variables.tf`, `outputs.tf`
2. Wire into root `main.tf` with `count = var.enable_<provider> ? 1 : 0`
3. Add feature flag `enable_<provider>` to `variables.tf`
4. Add provider-scoped budget entry in `modules/budget/variables.tf`
5. Add environment values in both `terraform.tfvars` files
