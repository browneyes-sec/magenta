# ADR-001: Multi-Cloud Provider Strategy

**Status:** Accepted  
**Date:** 2026-06-14  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture, Security, FinOps  

---

## Context

Magenta ASOAR needs a cloud infrastructure strategy that balances cost, compliance, security integration, and disaster recovery. The platform must:

- Integrate natively with Microsoft Sentinel (SIEM) and Entra ID (IAM) — the primary security toolchain.
- Support IL5 regulated workloads (US Gov / private cloud) for defense and intelligence customers.
- Provide geographic redundancy for disaster recovery.
- Stay within predictable monthly cost envelopes.

Initial analysis considered three fundamental approaches: single-cloud (Azure-only), dual-cloud (Azure + AWS), and multi-cloud with private cloud (Azure + AWS + vSphere). Each option was evaluated against security integration depth, compliance scope, operational complexity, and total cost.

---

## Decision

Adopt a **multi-cloud strategy with three tiers**:

| Tier | Provider | Allocation | Role |
|---|---|---|---|
| **Primary** | Microsoft Azure | 65% | Main compute, Sentinel SIEM, Entra ID, data lake, AI/ML |
| **Secondary** | Amazon Web Services | 25% | DR failover, cross-cloud redundancy, cost arbitrage |
| **Private** | VMware vSphere | 10% | IL5 regulated workloads, air-gapped deployments |

**Key implementation rules:**
1. Azure is the **control plane**: all Terraform state, monitoring, and CI/CD pipelines live in Azure.
2. AWS is **secondary-only**: no data at rest in AWS without Azure replica; failover is active-passive.
3. vSphere is **IL5-gated**: workloads tagged with `data-classification: il5` deploy to vSphere only.
4. Cost allocation is enforced via Azure budgets (overall + per-provider) with alert thresholds at 50/80/95%.

---

## Consequences

### Positive
- Deep Sentinel + Entra ID integration on Azure without abstraction layers.
- IL5 compliance without compromising Azure tooling (vSphere handles regulated data only).
- AWS provides genuine DR isolation — no single-cloud blast radius.
- Cost allocation rules map 1:1 to the FinOps tooling already built (`finops_tag_compliance`, budget module).

### Negative
- Higher operational complexity than single-cloud (3 provider SDKs, 3 sets of Terraform modules).
- Cross-cloud networking requires Transit Gateway + Azure Virtual WAN peering (see ADR-009).
- Team must maintain expertise in Azure, AWS, and vSphere.
- Not all workloads can be migrated freely — IL5 data is pinned to vSphere.

### Risks
- vSphere skill availability in the team.
- AWS underutilization if DR is never triggered (mitigated by running secondary dev/staging on AWS).

---

## Compliance

This decision is enforced by:
- **Cost allocation**: `soa/config/multicloud.toml` — hard-coded 0.65/0.25/0.10 percentages.
- **Terraform feature flags**: `enable_azure`, `enable_aws`, `enable_vsphere` in `soa/terraform/providers.tf`.
- **Tag audit**: `finops-gate.yml` CI workflow checks provider tags on every PR.
- **Budget module**: `soa/terraform/modules/budget/` creates per-provider budgets matching the allocation.

---

## Notes

- GCP is available but **not enabled** by default (`enable_gcp = false`). Can be activated if a customer requires GCP-native services (e.g., Vertex AI).
- Edge/k3s is defined in `providers.toml` but not yet implemented in Terraform — deferred to post-MVP.
- Allocation percentages are revisited quarterly during FinOps review.
