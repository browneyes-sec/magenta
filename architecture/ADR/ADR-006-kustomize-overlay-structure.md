# ADR-006: Kustomize Overlay Structure

**Status:** Accepted  
**Date:** 2026-06-14  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture  

---

## Context

Magenta SOA deploys 5+ Kubernetes services (mcp-bridge, agent-ops, agent-orchestrator, mcp-finops, mcp-web) across 3 environments (dev, staging, production). Each environment requires different replica counts, resource limits, image tags, PVC sizes, and TLS settings.

Three approaches were evaluated:
1. **Helm charts** — parameterized templates with `values.yaml` per environment.
2. **Plain YAML with sed/envsubst** — template-free but fragile.
3. **Kustomize overlays** — native `kubectl` patching without templates.

---

## Decision

Use **Kustomize 3-tier overlays**: `base/` → `overlays/{dev,staging,production}/`.

**Structure:**
```
soa/kubernetes/
├── base/
│   └── kustomization.yaml       # Shared: all resources, config maps, image defaults
├── overlays/
│   ├── dev/
│   │   └── kustomization.yaml   # 1 replica, dev tags, minimal resources
│   ├── staging/
│   │   └── kustomization.yaml   # 2 replicas, staging tags, 10Gi PVCs
│   └── production/
│       └── kustomization.yaml   # 3 replicas, 0.1.0 tags, 50Gi PVCs, tolerations
├── agents/                      # Agent deployment manifests
├── mcp-services/                # Service manifests
├── namespaces/                  # Namespace manifests
└── minikube/                    # Local dev scripts
```

**Why Kustomize over Helm:**
- **Zero template syntax**: YAML in, YAML out — no `{{ .Values.foo }}` to debug.
- **Native kubectl**: `kubectl apply -k overlays/production` — no tiller, no helm install.
- **Strategic merge patches**: overlays can patch any field without redefining the entire resource.
- **ConfigMap/Secret generation**: native `configMapGenerator` and `secretGenerator` with content hashing.
- **No package management**: Helm requires a chart repository; Kustomize reads from the filesystem.

---

## Consequences

### Positive
- PRs show exact YAML changes between environments — no template evaluation needed.
- Adding a new service = adding one manifest + one line in `base/kustomization.yaml`.
- Environment-specific overrides are explicit (all in overlay files) — not scattered across `values.yaml` inheritance.
- CI can validate overlays independently: `kustomize build overlays/dev | kubectl apply --dry-run=client -f -`.

### Negative
- No parameterized conditionals (e.g., "if production, enable X") — must use patch files.
- Large overlays can become repetitive if many resources need the same patch.
- No built-in dependency ordering (not needed for SOA — all services are stateless).

### Risks
- Patch conflicts if multiple overlays target the same field — mitigated by keeping overlays environment-specific, not composable.
- Secret management in Kustomize is limited to `secretGenerator` from files/env — production secrets use external-secrets-operator (future).

---

## Compliance

Enforced by:
- **Top-level `kustomization.yaml`**: backward-compatible entry point (references all manifests directly).
- **`base/kustomization.yaml`**: normalized source of truth for overlay inheritance.
- **Overlay files**: each environment's `kustomization.yaml` patches `spec.replicas`, `spec.template.spec.containers[0].resources`, and image tags.
- **All manifests**: use `app.kubernetes.io/name`, `app.kubernetes.io/component` labels for consistent selector matching.

---

## Notes

- The `minikube/start.sh` script applies the top-level `kustomization.yaml` (not overlays) for simplicity.
- Future: add `postrender` hooks or `kustomize edit` for dynamic image tags in CI.
