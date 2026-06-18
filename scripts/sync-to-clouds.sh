#!/usr/bin/env bash
# Magenta Air-Gap Image Sync Script
# Syncs golden images from GHCR to per-cloud registries (ACR, ECR, Artifact Registry).
# Usage: ./sync-to-clouds.sh [tag] [registry]
#
# Examples:
#   ./sync-to-clouds.sh sha-abc1234 all
#   ./sync-to-clouds.sh sha-abc1234 acr
#   ./sync-to-clouds.sh sha-abc1234 ecr
#   ./sync-to-clouds.sh sha-abc1234 gar
#
# Prerequisites:
#   - skopeo installed
#   - cosign installed
#   - Azure CLI authenticated (az acr login)
#   - AWS CLI authenticated (aws ecr get-login-password)
#   - gcloud CLI authenticated (gcloud auth configure-docker)
#
# See ADR-016 for architecture details.

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────

GHCR_REGISTRY="ghcr.io"
GHCR_ORG="browneyes-sec"  # GitHub org
GHCR_PREFIX="${GHCR_REGISTRY}/${GHCR_ORG}/magenta"

# Per-cloud registry URLs (set via environment or override)
ACR_URL="${ACR_URL:-}"
ECR_URL="${ECR_URL:-}"
GAR_URL="${GAR_URL:-}"

# Images to sync
IMAGES=(
  "base"
  "base-gpu"
  "base-collector"
  "base-tf-sidecar"
  "api"
  "worker"
  "scheduler"
  "agent-ops"
  "agent-orchestrator"
  "mcp-bridge"
  "web-gateway"
  "collector"
)

# ── Functions ──────────────────────────────────────────────────────────────

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

error() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: $*" >&2
  exit 1
}

check_deps() {
  for cmd in skopeo cosign; do
    if ! command -v "$cmd" &>/dev/null; then
      error "Required tool not found: $cmd"
    fi
  done
}

sync_to_acr() {
  local tag="$1"
  local image="$2"
  local src="${GHCR_PREFIX}/${image}:${tag}"
  local dst="${ACR_URL}/magenta/${image}:${tag}"

  log "Syncing ${src} → ${dst}"
  skopeo copy "docker://${src}" "docker://${dst}"

  # Verify signature
  log "Verifying signature on ${dst}"
  cosign verify --identity "https://token.actions.githubusercontent.com" \
    "docker://${dst}" 2>/dev/null || log "WARNING: Signature verification failed for ${dst}"
}

sync_to_ecr() {
  local tag="$1"
  local image="$2"
  local src="${GHCR_PREFIX}/${image}:${tag}"
  local dst="${ECR_URL}/magenta/${image}:${tag}"

  log "Syncing ${src} → ${dst}"
  skopeo copy "docker://${src}" "docker://${dst}"

  # Verify signature
  log "Verifying signature on ${dst}"
  cosign verify --identity "https://token.actions.githubusercontent.com" \
    "docker://${dst}" 2>/dev/null || log "WARNING: Signature verification failed for ${dst}"
}

sync_to_gar() {
  local tag="$1"
  local image="$2"
  local src="${GHCR_PREFIX}/${image}:${tag}"
  local dst="${GAR_URL}/magenta/${image}:${tag}"

  log "Syncing ${src} → ${dst}"
  skopeo copy "docker://${src}" "docker://${dst}"

  # Verify signature
  log "Verifying signature on ${dst}"
  cosign verify --identity "https://token.actions.githubusercontent.com" \
    "docker://${dst}" 2>/dev/null || log "WARNING: Signature verification failed for ${dst}"
}

# ── Main ───────────────────────────────────────────────────────────────────

main() {
  local tag="${1:-latest}"
  local registry="${2:-all}"

  check_deps

  log "Starting sync for tag=${tag} registry=${registry}"

  case "$registry" in
    acr)
      [[ -z "$ACR_URL" ]] && error "ACR_URL not set"
      for image in "${IMAGES[@]}"; do
        sync_to_acr "$tag" "$image"
      done
      ;;
    ecr)
      [[ -z "$ECR_URL" ]] && error "ECR_URL not set"
      for image in "${IMAGES[@]}"; do
        sync_to_ecr "$tag" "$image"
      done
      ;;
    gar)
      [[ -z "$GAR_URL" ]] && error "GAR_URL not set"
      for image in "${IMAGES[@]}"; do
        sync_to_gar "$tag" "$image"
      done
      ;;
    all)
      [[ -z "$ACR_URL" ]] && error "ACR_URL not set"
      [[ -z "$ECR_URL" ]] && error "ECR_URL not set"
      [[ -z "$GAR_URL" ]] && error "GAR_URL not set"
      for image in "${IMAGES[@]}"; do
        sync_to_acr "$tag" "$image"
        sync_to_ecr "$tag" "$image"
        sync_to_gar "$tag" "$image"
      done
      ;;
    *)
      error "Unknown registry: ${registry}. Use: acr, ecr, gar, or all"
      ;;
  esac

  log "Sync complete"
}

main "$@"
