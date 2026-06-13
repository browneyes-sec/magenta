# Magenta SOA — Terraform IaC
# Multi-cloud infrastructure provisioning for the SOA layer.

## Directory Structure

```
terraform/
├── main.tf                        # Root module — orchestrates all providers
├── providers.tf                   # Cloud provider configs + shared variables
├── modules/
│   ├── compute/                   # VM + K8s compute (Azure AKS, AWS EKS, GCP GKE)
│   │   ├── main.tf
│   │   └── variables.tf
│   └── kubernetes/                # K8s cluster + Helm add-ons (MCP bridge, Qdrant, Redis)
│       ├── main.tf
│       └── variables.tf
└── environments/
    └── dev/
        ├── terraform.tfvars       # Dev-specific values
        └── backend.tf             # Remote state backend
```

## Usage

```bash
# 1. Initialize dev environment
cd terraform/environments/dev
terraform init

# 2. Validate configuration
terraform validate

# 3. Plan infrastructure
terraform plan -var-file=terraform.tfvars

# 4. Apply via Agent Ops (MCP tool) or directly
terraform apply -var-file=terraform.tfvars

# 5. Agent Ops drift detection
mcp call agent-ops.iac_drift_detect --environment dev
```

## Provider Agnostic Design

- All modules accept a `provider` parameter (`azure`, `aws`, `gcp`, `vsphere`)
- Common variables: `environment`, `location`, `vm_sku`, `node_count`, `tags`
- Tagging follows FinOps standards: `cost-center`, `environment`, `project`, `managed-by`
- Conditional resource creation via `count` + `enable_*` booleans

## Cost Governance

Every resource is tagged with:
- `cost-center` — maps to budget owner
- `environment` — dev/staging/production
- `project` — aggregates all magenta resources
- `managed-by` — allows Agent Ops to discover and manage

Agent Ops `finops_tag_compliance` validates these tags across all providers.

## Adding a Provider

1. Add provider config in `providers.tf`
2. Add `enable_<provider>` variable
3. Add module instantiation in `main.tf` with `count = var.enable_<provider> ? 1 : 0`
4. Add environment-specific values in `environments/<env>/terraform.tfvars`
