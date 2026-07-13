# ADR-009: Hub-and-Spoke Multi-Cloud Networking

**Status:** Accepted  
**Date:** 2026-06-14  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture, Network Engineering  

---

## Context

Magenta deploys workloads across Azure (primary), AWS (DR), and vSphere (IL5). These workloads must communicate securely:

- Agent Ops in Azure AKS must reach AWS EC2 instances for `cloud_discover` operations.
- Vector store (Qdrant) in Azure must replicate to AWS Elasticache for DR.
- IL5 workloads in vSphere must be network-isolated from public cloud but reachable by authorized agents.

Three topologies were evaluated:
1. **Mesh VPN** (WireGuard/Tailscale) — peer-to-peer encrypted tunnels.
2. **Direct peering** — Azure VNet peering + AWS VPC peering + GCP VPC peering, no central hub.
3. **Hub-and-spoke** — a central hub VPC/VNet with spokes for each provider and workload.

---

## Decision

Use **hub-and-spoke topology** with Azure as the hub:

```
                    ┌──────────────────┐
                    │  Azure Hub VNet  │
                    │  (10.0.0.0/16)   │
                    │                  │
                    │  ┌── Transit ──┐ │
                    │  │  Gateway    │ │
                    │  └─────────────┘ │
                    └────────┬─────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                   ▼
   ┌─────────────┐   ┌─────────────┐   ┌────────────────┐
   │ Azure Spoke │   │ AWS Spoke   │   │ vSphere Spoke  │
   │ VNets       │   │ VPC (TGW)   │   │ (VPN + VLAN)   │
   │ AKS, Redis  │   │ EKS, RDS    │   │ Self-managed   │
   │ Qdrant      │   │ ElastiCache │   │ K8s + VMs      │
   └─────────────┘   └─────────────┘   └────────────────┘
```

**Implementation per provider:**
- **Azure hub**: Virtual WAN (vWAN) with hub VNet peering to spoke VNets.
- **AWS spoke**: Transit Gateway (TGW) attached to hub VPC, route propagation to spoke VPCs.
- **vSphere spoke**: Site-to-Site VPN (IPsec) from Azure VPN Gateway to vSphere Edge Gateway.

---

## Consequences

### Positive
- All cross-cloud traffic flows through a single hub — simplified network policy, firewalls, and audit logging.
- Azure (primary cloud) is the natural hub — reduces egress costs since most traffic stays within Azure.
- AWS and vSphere spokes are "dumb pipes" — no complex routing, just TGW attachments and VPN tunnels.
- Adding a new provider/region = adding a new spoke — hub remains unchanged.

### Negative
- Hub is a single point of failure for cross-cloud traffic (mitigated by active-passive with AWS as DR).
- Azure egress costs for traffic to AWS/vSphere (≈$0.02/GB — roughly 5% of monthly budget).
- VPN to vSphere adds ~5ms latency (acceptable for management-plane traffic, not for real-time).

### Risks
- Azure vWAN service limits — mitigated by requesting quota increases before production rollout.
- IPsec tunnel stability to vSphere — mitigated by redundant tunnels on two separate edge gateways.
- Route table explosion with many spokes — mitigated by using Azure Route Server + BGP.

---

## Compliance

Enforced by:
- **Network Terraform module**: `soa/terraform/modules/network/main.tf` defines the hub VNet, subnets, AWS TGW, and GCP VPC.
- **CIDR allocation**: Azure `10.0.0.0/16`, AWS `10.1.0.0/16`, GCP `10.2.0.0/16`, vSphere `192.168.0.0/16` — no overlap.
- **Environment tfvars**: `environments/staging/` and `environments/production/` each set their hub CIDRs.
- **Root main.tf**: the `network_hub` module is gated by `enable_network_hub` flag.

---

## Notes

- GCP is defined in the network module but not enabled by default — will be activated when `enable_gcp = true`.
- The vSphere VPN uses IKEv2 with PSK stored in Azure Key Vault (not Terraform state).
- Network monitoring: all spoke-hub traffic is logged to Azure Network Watcher + Log Analytics.
