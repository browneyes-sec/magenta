# Magenta SOA — Kubernetes Module
# Provisions and configures managed Kubernetes clusters.

terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
    aws     = { source = "hashicorp/aws" }
    google  = { source = "hashicorp/google" }
    helm    = { source = "hashicorp/helm" }
  }
}

variable "provider" { type = string }
variable "environment" { type = string }
variable "location" { type = string }
variable "cluster_name" { type = string }
variable "node_pool_sku" { type = string }
variable "node_count" { type = number }
variable "service_cidr" { type = string }
variable "tags" { type = map(string) }

# ── MCP Service Mesh Add-ons (Helm) ──────────────────────────────────────

resource "helm_release" "mcp_bridge" {
  count      = 1
  name       = "mcp-bridge"
  repository = "oci://ghcr.io/magenta/charts"
  chart      = "mcp-bridge"
  namespace  = "magenta-soa"
  version    = "1.0.0"

  set {
    name  = "replicaCount"
    value = var.environment == "production" ? "3" : "1"
  }
  set {
    name  = "ingress.enabled"
    value = "true"
  }
}

resource "helm_release" "qdrant" {
  count      = 1
  name       = "qdrant"
  repository = "https://qdrant.github.io/qdrant-helm"
  chart      = "qdrant"
  namespace  = "magenta-soa"
  version    = "0.1.0"

  values = [yamlencode({
    replicaCount = var.environment == "production" ? 3 : 1
    persistence  = { size = var.environment == "production" ? "100Gi" : "10Gi" }
    grpc         = { enabled = true }
  })]
}

resource "helm_release" "redis" {
  count      = 1
  name       = "redis"
  repository = "oci://registry-1.docker.io/bitnamicharts"
  chart      = "redis"
  namespace  = "magenta-soa"
  version    = "20.0"

  values = [yamlencode({
    architecture = "standalone"
    auth = { enabled = true, existingSecret = "redis-secret" }
    master = {
      resources = { requests = { cpu = "500m", memory = "1Gi" } }
    }
  })]
}

# ── Outputs ──────────────────────────────────────────────────────────────

output "helm_releases" {
  value = ["mcp-bridge", "qdrant", "redis"]
}
