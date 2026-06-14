# ADR-005: Per-Provider Kubernetes Module Decomposition

**Status:** Accepted  
**Date:** 2026-06-14  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture  

---

## Context

The original `soa/terraform/modules/compute/main.tf` used a single monolithic module with `count` and `var.provider` conditionals to support Azure (AKS), AWS (EKS), and GCP (GKE):

```terraform
resource "azurerm_kubernetes_cluster" "this" {
  count = var.provider == "azure" ? 1 : 0
  ...
}
resource "aws_eks_cluster" "this" {
  count = var.provider == "aws" ? 1 : 0
  ...
}
```

As the codebase grew to include vSphere (VM-based K8s), private clusters, Azure AD RBAC, EKS IRSA, GKE workload identity, and user node pools with taints, the monolithic module became unwieldy. The `var.provider` conditionals created a combinatorial explosion of `dynamic` blocks and nested `try()` expressions.

---

## Decision

Decompose into **per-provider dedicated modules**:

| Module | Path | Provider | Key Features |
|---|---|---|---|
| **aks** | `modules/aks/` | Azure | AAD RBAC, private cluster, system+user pools, container insights, autoscaler |
| **eks** | `modules/eks/` | AWS | IRSA/OIDC, managed node groups, VPC CNI addon, audit logging, node taints |
| **gke** | `modules/gke/` | GCP | Workload identity, VPC-native, shielded nodes, release channels, netpol |
| **vsphere** | `modules/vsphere/` | vSphere | VM template cloning, static IPs, control-plane/worker split |

**Migration strategy (backward compatible):**
- Old `modules/compute/` and `modules/kubernetes/` remain unchanged.
- Root `main.tf` uses a feature flag `use_new_k8s_modules` (default: `false`).
- When `true`, old modules become `count = 0` and new modules activate.
- Staging and production tfvars set `use_new_k8s_modules = true`.

---

## Consequences

### Positive
- Each module is self-contained with its own `variables.tf` — no shared variable namespace pollution.
- Provider-specific features (IRSA, AAD RBAC, workload identity) are first-class, not `dynamic` blocks.
- Adding a new provider (e.g., GCP for a specific customer) doesn't touch existing module code.
- Module interfaces are explicit — no implicit `var.provider == "azure"` branching.

### Negative
- Code duplication across modules (similar resource patterns repeated for each provider).
- Root `main.tf` is longer (dual-path module declarations).
- Engineers must learn 4 module interfaces instead of 1 generic one.

### Risks
- Drift between module capabilities — mitigated by the `k8s_*` shared variables in root `variables.tf`.
- Old modules become stale if `use_new_k8s_modules=true` is the default — mitigated by the plan to deprecate old modules in Sprint 5.

---

## Compliance

Enforced by:
- **Root main.tf**: dual-path with `use_new_k8s_modules` toggle (line ~55 for old, line ~165 for new).
- **Root variables.tf**: `k8s_system_node_sku`, `k8s_user_node_pools`, etc. shared by all new modules.
- **Tfvars**: `environments/staging/terraform.tfvars` and `environments/production/terraform.tfvars` both set `use_new_k8s_modules = true`.

---

## Notes

- The sku translation `Standard_D4s_v5` → `t3.medium` (EKS) / `e2-standard-4` (GKE) uses Terraform `replace()` as a temporary measure. Future: a mapping variable in root `variables.tf`.
- vSphere module uses self-managed K8s (kubeadm) — unlike managed AKS/EKS/GKE. This is intentional: vSphere doesn't offer managed K8s.
