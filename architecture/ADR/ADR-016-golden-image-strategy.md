# ADR-016: Golden Image Strategy with GPU/OLLAMA Support

**Status:** Accepted
**Date:** 2026-06-18
**Authors:** Platform Architecture Team
**Deciders:** Platform Architecture, Security, Engineering, FinOps

---

## Context

Magenta ASOAR currently uses 8 service Dockerfiles all built on `python:3.12-slim` (~120MB base) with no distroless optimization, no GPU-enabled variants for OLLAMA inference, and no supply chain security (signing, SBOM, scanning). The Agent Ops image bakes in Terraform + 3 cloud CLIs (~1.5GB), making it 5-6× heavier than other services. Air-gapped production requires per-cloud registry sync (ACR, ECR, Artifact Registry) with keyless OIDC signing via cosign, migrating to hardware-backed KMS later.

### Current State Assessment

| Dimension | Score | Status |
|-----------|-------|--------|
| Dockerfile Maturity | 4/10 | Fragmented, no distroless, no GPU variants |
| GPU/OLLAMA Readiness | 3/10 | No GPU-enabled images, no NVIDIA toolkit in containers |
| Supply Chain Security | 2/10 | No signing, SBOM, scanning, or promotion gates |
| Multi-Cloud Registry Strategy | 0/10 | GHCR only, no air-gap sync, no per-cloud registry wiring |

### Fitness Baseline (Dockerfiles)

| Service | Base Image | Est. Size | GPU Ready | Issues |
|---------|------------|-----------|-----------|--------|
| agent-ops | python:3.12-slim | ~1.5 GB | No | Terraform + 3 CLIs baked in; should be sidecars |
| api | python:3.12-slim | ~300 MB | No | Standard pattern, good candidate for distroless |
| worker | python:3.12-slim | ~300 MB | No | Same as API |
| scheduler | python:3.12-slim | ~250 MB | No | Minimal deps |
| agent-orchestrator | python:3.12-slim | ~280 MB | No | No config/terraform copy |
| mcp-bridge | python:3.12-slim | ~280 MB | No | grpcurl added |
| collector | python:3.12-slim | ~400 MB | No | Build deps left in runtime |
| web-gateway | python:3.12-slim | ~280 MB | No | Lightweight |
| OLLAMA (data mesh) | ollama/ollama:0.5.7 | ~4-8 GB | Compose only | GPU via deploy.resources only |
| OLLAMA (MVS) | ollama/ollama:latest | ~4-8 GB | Compose only | No model pre-bake, no GPU in Dockerfile |

### Fitness Baseline (Terraform GPU)

| Module | GPU Support | Security Hardening | Grade |
|--------|-------------|-------------------|-------|
| AKS | Standard_NC*_v3/v4 SKUs | No Pod Security Policy | B+ |
| EKS | g5/p4/inf2 via node group | No Pod Security Admission | B |
| GKE | a2-highgpu-* via node pool | No Binary Auth | B |
| vSphere | No GPU VM class | No VM encryption | C+ |

---

## Decision

Implement a **layered golden image hierarchy** with distroless base images, GPU-enabled variants for LLM inference, Agent Ops sidecar decomposition, and a CI/CD pipeline with supply chain security (scanning, SBOM, signing, air-gap sync).

### Key Design Rules

1. **Distroless by default.** All service images use `chainguard/python:3.12` or `gcr.io/distroless/python3-debian12` as base. Hardened slim deferred for production only.

2. **GPU variant separation.** GPU images extend the CPU base with NVIDIA toolkit (`nvidia-container-toolkit`, `libcuda1`, `nvidia-ml`). OLLAMA inference images use this variant.

3. **Agent Ops decomposition.** Split Agent Ops into two images:
   - `magenta/agent-ops-core` (~300MB): Python runtime + MCP tools
   - `magenta/agent-ops-tf-sidecar` (~800MB): Terraform + Azure CLI + AWS CLI + gcloud SDK
   Run as separate pods in K8s.

4. **Collector minimalism.** Single-stage with build deps cleaned; non-root user (uid 10001).

5. **Multi-arch builds.** All images build for `linux/amd64` and `linux/arm64`.

6. **Digest pinning.** Base images pinned by SHA256 digest; automated rebuild on CVE via Dependabot.

7. **Supply chain security.** CI pipeline: build → scan (trivy) → SBOM (syft) → sign (cosign keyless) → push to GHCR → promote to per-cloud registries.

8. **Air-gap sync.** `skopeo` copy GHCR → ACR/ECR/Artifact Registry with digest verification.

9. **KMS preconfiguration.** Keyless OIDC for dev/staging; hardware KMS (AWS KMS / Azure Key Vault / GCP KMS) preconfigured in Terraform for prod migration.

---

## Consequences

### Positive

- **5-6× smaller Agent Ops image**: Split saves ~1.2GB/image × 7 services = ~8.4GB registry savings.
- **GPU-native OLLAMA images**: Pre-pulled models, NVIDIA toolkit, RuntimeClass-ready.
- **Supply chain integrity**: Signed images, SBOM attestation, vulnerability scanning gates.
- **Air-gap ready**: Per-cloud registry sync with digest verification.
- **Debuggability**: Distroless images support `kubectl debug` and cdebug sidecar.
- **Cost reduction**: Smaller images → faster pulls, lower registry storage, faster pod startup.

### Negative

- **Complexity**: 3-tier image hierarchy (base → service → sidecar) requires documentation.
- **Debugging difficulty**: Distroless lacks shell; requires `kubectl debug` or busybox sidecar.
- **NVIDIA dependency**: GPU images require host NVIDIA driver + container toolkit.
- **Registry auth overhead**: Per-cloud registry sync requires IAM federation (GitHub Actions → cloud IAM).

### Mitigations

- **Debugging**: Document `kubectl debug` and `cdebug` patterns in operational runbooks.
- **NVIDIA**: Deploy NVIDIA GPU Operator via Terraform; document driver version matrix.
- **Registry auth**: Use OIDC federation (GitHub Actions → cloud IAM) for zero-secret CI.

---

## Implementation

### Phase 1: Base Images + Dockerfile Refactor (Days 1-2)

| File | Description |
|------|-------------|
| `soa/docker/base/Dockerfile.distroless` | CPU base image (chainguard/python:3.12) |
| `soa/docker/base/Dockerfile.gpu` | GPU base image (distroless + nvidia-toolkit) |
| `soa/docker/base/Dockerfile.collector` | Collector base (distroless + gcc/krb5 for paramiko) |
| `soa/docker/base/Dockerfile.tf-sidecar` | Terraform + cloud CLIs sidecar |

Refactor all 7 service Dockerfiles to `FROM magenta/base:distroless`.

### Phase 2: CI/CD Pipeline (Days 2-3)

| File | Description |
|------|-------------|
| `.github/workflows/golden-images.yml` | Matrix build, scan, sign, push |
| `.github/workflows/registry-sync.yml` | Promote to ACR/ECR/Artifact Registry |
| `.github/workflows/airgap-export.yml` | skopeo copy to tarball for air-gap |

### Phase 3: Terraform GPU Operator (Days 3-4)

| File | Description |
|------|-------------|
| `soa/terraform/modules/gpu-operator/` | NVIDIA GPU Operator (Helm or direct) |
| `soa/terraform/modules/aks/variables.tf` | GPU RuntimeClass support |
| `soa/terraform/modules/eks/variables.tf` | GPU IRSA for OLLAMA |
| `soa/terraform/modules/gke/variables.tf` | GPU Binary Auth integration |

### Phase 4: K8s Manifests + Validation (Days 4-5)

| File | Description |
|------|-------------|
| `soa/kubernetes/base/agent-ops/` | Core + sidecar deployment |
| `soa/kubernetes/base/ollama-gpu/` | GPU inference with RuntimeClass |
| `soa/kubernetes/base/network/` | Default deny NetworkPolicy |
| `soa/kubernetes/overlays/{dev,staging,prod}/` | Per-env image overrides |

---

## Compliance

| ADR-016 Provision | ADR-010 (Data Mesh) | ADR-005 (Per-Provider) | ADR-009 (Network) | ADR-008 (FinOps) |
|---|---|---|---|---|
| distroless base | Smaller vectorizer image | Per-provider registry sync | Faster pod startup | Lower registry cost |
| GPU images | OLLAMA in mesh | GPU node pool per provider | GPU traffic isolation | GPU cost allocation |
| Sidecar pattern | Sidecar for vectorizer | Sidecar per provider | Sidecar network policy | Sidecar cost tracking |
| Air-gap sync | Mesh gateway sync | Per-cloud registry | Network isolation | Sync cost tracking |

---

## Appendix: GPU Node Pool SKUs

| Cloud | SKU | GPU | VRAM | Use Case | Cost/mo (730h) |
|-------|-----|-----|------|----------|----------------|
| Azure | Standard_NC24s_v3 | 4× V100 16GB | 64 GB | Staging | ~$1,200 |
| Azure | Standard_NC48ads_A100_v4 | 4× A100 80GB | 320 GB | Production | ~$4,500 |
| AWS | g5.xlarge | 1× A10G 24GB | 24 GB | Burst/Staging | ~$350 |
| AWS | g5.4xlarge | 1× A10G 24GB | 24 GB | Production | ~$1,400 |
| GCP | a2-highgpu-1g | 1× A100 80GB | 80 GB | Production | ~$3,200 |
| vSphere | NVIDIA A40 | 1× A40 48GB | 48 GB | IL5 regulated | ~$2,000 |

---

## Appendix: Model → GPU Assignment

| Agent Role | Model | VRAM | GPU Tier | Max Concurrent |
|------------|-------|------|----------|----------------|
| Swarm Manager | mixtral:8x7b | ~23 GB | A100 80GB | 3 |
| Investigation | qwen2.5:32b | ~18 GB | A100 80GB | 4 |
| Triage | qwen2.5:7b | ~6 GB | RTX 4090 24GB | 3-4 |
| Containment | mistral:7b | ~6 GB | RTX 4090 24GB | 3-4 |
| Enrich | mistral:7b | ~6 GB | RTX 4090 24GB | 3-4 |
| Compliance | phi4:14b | ~10 GB | RTX 4090 24GB | 2 |
| Reporting | qwen2.5:7b (CPU) | ~6 GB | CPU | 10 |
| High-Volume Filter | nemotron-mini:4b | ~3 GB | CPU | 20 |

---

## Deferred Technical Practices (DTPs)

| # | DTP | Owner | Target | Notes |
|---|-----|-------|--------|-------|
| 1 | Hardware KMS signing (AWS/Azure/GCP) | Security | Week 6 | Replace cosign keyless with KMS-backed |
| 2 | SLSA Level 3 build provenance | CI/CD | Week 8 | Add slsa-verifier to workflow |
| 3 | Automated base image rebuild on CVE | Security | Week 4 | Dependabot + rebuild pipeline |
| 4 | Kyverno/OPA admission controller for image signature | K8s | Week 8 | Block unsigned images in prod |
| 5 | Registry replication + geo-redundant image cache | Infra | Week 10 | DR for air-gap environments |
| 6 | SBOM vulnerability monitoring (OSV/Grype scheduled scans) | Security | Week 6 | Weekly scan of all prod images |
| 7 | vSphere GPU passthrough + VM encryption | Infra | Week 6 | IL5 regulated workloads |
| 8 | Cloud burst automation (TF + K8s autoscaler) | Platform | Week 8 | Auto-provision spot GPU on queue depth |
