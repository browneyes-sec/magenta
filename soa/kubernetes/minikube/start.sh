#!/usr/bin/env bash
# Magenta SOA — Minikube Quickstart
# Starts a local minikube cluster with the SOA mesh pre-configured.
# Optional: pass --vm-driver=docker for container-based, --vm-driver=kvm2 for VM-based.

set -euo pipefail

CLUSTER_NAME="${MAGENTA_CLUSTER_NAME:-magenta-soa}"
MINIKUBE_DRIVER="${MINIKUBE_DRIVER:-docker}"
MINIKUBE_CPUS="${MINIKUBE_CPUS:-4}"
MINIKUBE_MEMORY="${MINIKUBE_MEMORY:-8192}"
MINIKUBE_DISK="${MINIKUBE_DISK:-20g}"
K8S_VERSION="${MAGENTA_K8S_VERSION:-v1.31.0}"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  Magenta SOA — Minikube Cluster Setup                       ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Cluster:   ${CLUSTER_NAME}"
echo "  Driver:    ${MINIKUBE_DRIVER}"
echo "  CPUs:      ${MINIKUBE_CPUS}"
echo "  Memory:    ${MINIKUBE_MEMORY} MB"
echo "  Disk:      ${MINIKUBE_DISK}"
echo "  K8s:       ${K8S_VERSION}"
echo ""

# ── Check prerequisites ──────────────────────────────────────────────

command -v minikube >/dev/null 2>&1 || {
  echo "ERROR: minikube not found. Install: https://minikube.sigs.k8s.io/docs/start/"
  exit 1
}
command -v kubectl >/dev/null 2>&1 || {
  echo "ERROR: kubectl not found."
  exit 1
}

# ── Start cluster ────────────────────────────────────────────────────

if minikube status --profile="${CLUSTER_NAME}" >/dev/null 2>&1; then
  echo "→ Cluster '${CLUSTER_NAME}' already running."
else
  echo "→ Starting minikube cluster '${CLUSTER_NAME}'..."
  minikube start \
    --profile="${CLUSTER_NAME}" \
    --driver="${MINIKUBE_DRIVER}" \
    --cpus="${MINIKUBE_CPUS}" \
    --memory="${MINIKUBE_MEMORY}" \
    --disk-size="${MINIKUBE_DISK}" \
    --kubernetes-version="${K8S_VERSION}" \
    --addons="ingress,metrics-server,metallb,registry" \
    --extra-config="kubelet.max-pods=110"
fi

echo ""
echo "→ Cluster info:"
minikube profile list | grep "${CLUSTER_NAME}" || true
echo ""

# ── Configure kubectl ────────────────────────────────────────────────

MINIKUBE_KUBECONFIG="${HOME}/.kube/config-${CLUSTER_NAME}"
minikube update-context --profile="${CLUSTER_NAME}"
echo "→ kubectl context: $(kubectl config current-context)"

# ── Verify node status ───────────────────────────────────────────────

echo ""
echo "→ Node status:"
kubectl get nodes -o wide

# ── Apply SOA manifests ──────────────────────────────────────────────

SOA_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "${SOA_DIR}/kustomization.yaml" ]; then
  echo ""
  echo "→ Deploying Magenta SOA layer..."
  kubectl apply -k "${SOA_DIR}/"
else
  echo ""
  echo "→ No kustomization.yaml found at ${SOA_DIR}; creating namespaces only."
  for ns in magenta-soa magenta-agents magenta-mesh magenta-finops; do
    kubectl create namespace "${ns}" --dry-run=client -o yaml | kubectl apply -f -
  done
fi

# ── Print access info ────────────────────────────────────────────────

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  Magenta SOA — Ready                                         ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Dashboard:  minikube dashboard --profile=${CLUSTER_NAME}"
echo "  Tunnel:     minikube tunnel --profile=${CLUSTER_NAME}"
echo "  Stop:       minikube stop --profile=${CLUSTER_NAME}"
echo "  Delete:     minikube delete --profile=${CLUSTER_NAME}"
echo ""
echo "  MCP Bridge: kubectl -n magenta-soa port-forward svc/mcp-bridge 8080:8080"
echo "  Agent Ops:  kubectl -n magenta-agents port-forward svc/agent-ops 50060:50060"
echo "  Qdrant:     kubectl -n magenta-soa port-forward svc/qdrant 6333:6333 6334:6334"
echo ""
