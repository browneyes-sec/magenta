# Magenta Data Mesh — Terraform Module
# Provisions Qdrant, Redis, OLLAMA, Elasticsearch for the data plane.

terraform {
  required_version = ">= 1.8.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.32"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.15"
    }
  }
}

# ── Variables ─────────────────────────────────────────────────────────────

variable "environment" {
  description = "Deployment environment"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Must be dev, staging, or production."
  }
}

variable "resource_prefix" {
  description = "Prefix for resource naming"
  type        = string
  default     = "magenta"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus2"
}

variable "common_tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
}

variable "embedding_model" {
  description = "OLLAMA embedding model"
  type        = string
  default     = "bge-m3"
}

variable "embedding_dimension" {
  description = "Embedding vector dimension"
  type        = number
  default     = 1024
}

variable "qdrant_replicas" {
  description = "Qdrant replica count"
  type        = number
  default     = 1
}

variable "qdrant_storage_gb" {
  description = "Qdrant persistent storage in GB"
  type        = number
  default     = 100
}

variable "redis_memory_mb" {
  description = "Redis max memory in MB"
  type        = number
  default     = 512
}

variable "ollama_gpu_enabled" {
  description = "Enable GPU for OLLAMA inference"
  type        = bool
  default     = false
}

variable "elasticsearch_enabled" {
  description = "Deploy Elasticsearch for hot registry"
  type        = bool
  default     = true
}

variable "elasticsearch_replicas" {
  description = "Elasticsearch replica count"
  type        = number
  default     = 1
}

variable "elasticsearch_storage_gb" {
  description = "Elasticsearch persistent storage in GB"
  type        = number
  default     = 50
}

variable "enable_sentinel_dcr" {
  description = "Enable Sentinel Data Collection Rule for SecurityAutomationActivity_CL"
  type        = bool
  default     = true
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID for DCR"
  type        = string
  default     = ""
}

variable "namespace" {
  description = "Kubernetes namespace for data mesh"
  type        = string
  default     = "magenta-mesh"
}

# ── Kubernetes Namespace ──────────────────────────────────────────────────

resource "kubernetes_namespace" "mesh" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/part-of" = "magenta-asoar"
      "app.kubernetes.io/component" = "data-mesh"
    }
  }
}

# ── Qdrant StatefulSet ───────────────────────────────────────────────────

resource "kubernetes_config_map" "qdrant_collections" {
  metadata {
    name      = "qdrant-collection-configs"
    namespace = kubernetes_namespace.mesh.metadata[0].name
  }

  data = {
    "siem_alerts.json" = jsonencode({
      vectors         = { size = var.embedding_dimension, distance = "Cosine" }
      hnsw_config     = { m = 16, ef_construct = 200 }
      optimizers_config = { default_segment_number = 2, memmap_threshold_kb = 20000 }
    })
    "mem_episodic.json" = jsonencode({
      vectors         = { size = var.embedding_dimension, distance = "Cosine" }
      hnsw_config     = { m = 16, ef_construct = 200 }
      optimizers_config = { default_segment_number = 2, memmap_threshold_kb = 20000 }
    })
    "mem_semantic.json" = jsonencode({
      vectors         = { size = var.embedding_dimension, distance = "Cosine" }
      hnsw_config     = { m = 16, ef_construct = 200 }
      optimizers_config = { default_segment_number = 2, memmap_threshold_kb = 20000 }
    })
    "mem_procedural.json" = jsonencode({
      vectors         = { size = var.embedding_dimension, distance = "Cosine" }
      hnsw_config     = { m = 16, ef_construct = 200 }
      optimizers_config = { default_segment_number = 2, memmap_threshold_kb = 20000 }
    })
  }
}

resource "kubernetes_stateful_set" "qdrant" {
  metadata {
    name      = "qdrant"
    namespace = kubernetes_namespace.mesh.metadata[0].name
    labels = {
      app       = "qdrant"
      component = "vector-store"
    }
  }

  spec {
    service_name = "qdrant"
    replicas     = var.qdrant_replicas

    selector {
      match_labels = {
        app = "qdrant"
      }
    }

    template {
      metadata {
        labels = {
          app       = "qdrant"
          component = "vector-store"
        }
      }

      spec {
        container {
          name  = "qdrant"
          image = "qdrant/qdrant:v1.12.0"

          port {
            name           = "http"
            container_port = 6333
          }
          port {
            name           = "grpc"
            container_port = 6334
          }

          env {
            name  = "QDRANT__SERVICE__GRPC_PORT"
            value = "6334"
          }
          env {
            name  = "QDRANT__SERVICE__HTTP_PORT"
            value = "6333"
          }
          env {
            name  = "QDRANT__LOG_LEVEL"
            value = "INFO"
          }

          resources {
            requests = {
              cpu    = "1"
              memory = "2Gi"
            }
            limits = {
              cpu    = "4"
              memory = "8Gi"
            }
          }

          volume_mount {
            name       = "qdrant-storage"
            mount_path = "/qdrant/storage"
          }

          readiness_probe {
            http_get {
              path = "/healthz"
              port = 6333
            }
            initial_delay_seconds = 10
            period_seconds        = 10
          }

          liveness_probe {
            http_get {
              path = "/healthz"
              port = 6333
            }
            initial_delay_seconds = 30
            period_seconds        = 20
          }
        }

        volume {
          name = "qdrant-storage"
          persistent_volume_claim {
            claim_name = "qdrant-pvc"
          }
        }
      }
    }
  }

  depends_on = [kubernetes_config_map.qdrant_collections]
}

resource "kubernetes_persistent_volume_claim" "qdrant" {
  metadata {
    name      = "qdrant-pvc"
    namespace = kubernetes_namespace.mesh.metadata[0].name
  }

  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = "${var.qdrant_storage_gb}Gi"
      }
    }
    storage_class_name = "standard"
  }
}

resource "kubernetes_service" "qdrant" {
  metadata {
    name      = "qdrant"
    namespace = kubernetes_namespace.mesh.metadata[0].name
  }

  spec {
    selector = {
      app = "qdrant"
    }

    port {
      name = "http"
      port = 6333
    }
    port {
      name = "grpc"
      port = 6334
    }

    cluster_ip = "None" # headless for StatefulSet
  }
}

# ── OLLAMA Deployment ─────────────────────────────────────────────────────

resource "kubernetes_deployment" "ollama" {
  metadata {
    name      = "ollama-embed"
    namespace = kubernetes_namespace.mesh.metadata[0].name
    labels = {
      app       = "ollama-embed"
      component = "embedding"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "ollama-embed"
      }
    }

    template {
      metadata {
        labels = {
          app       = "ollama-embed"
          component = "embedding"
        }
      }

      spec {
        container {
          name  = "ollama"
          image = "ollama/ollama:0.5.7"

          port {
            name           = "http"
            container_port = 11434
          }

          command = [
            "sh", "-c",
            "ollama serve & sleep 5 && ollama pull ${var.embedding_model} && wait"
          ]

          resources {
            requests = {
              cpu    = "500m"
              memory = "1Gi"
            }
            limits = {
              cpu    = var.ollama_gpu_enabled ? "4" : "2"
              memory = var.ollama_gpu_enabled ? "8Gi" : "4Gi"
            }
          }

          readiness_probe {
            http_get {
              path = "/api/health"
              port = 11434
            }
            initial_delay_seconds = 15
            period_seconds        = 15
          }

          volume_mount {
            name       = "ollama-data"
            mount_path = "/root/.ollama"
          }
        }

        volume {
          name = "ollama-data"
          empty_dir {}
        }
      }
    }
  }
}

resource "kubernetes_service" "ollama" {
  metadata {
    name      = "ollama-embed"
    namespace = kubernetes_namespace.mesh.metadata[0].name
  }

  spec {
    selector = {
      app = "ollama-embed"
    }

    port {
      port = 11434
    }
  }
}

# ── Redis Deployment ──────────────────────────────────────────────────────

resource "kubernetes_deployment" "redis" {
  metadata {
    name      = "redis"
    namespace = kubernetes_namespace.mesh.metadata[0].name
    labels = {
      app       = "redis"
      component = "cache"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "redis"
      }
    }

    template {
      metadata {
        labels = {
          app       = "redis"
          component = "cache"
        }
      }

      spec {
        container {
          name  = "redis"
          image = "redis:7.4-alpine"

          port {
            container_port = 6379
          }

          command = [
            "redis-server",
            "--appendonly", "yes",
            "--maxmemory", "${var.redis_memory_mb}mb",
            "--maxmemory-policy", "allkeys-lru"
          ]

          resources {
            requests = {
              cpu    = "250m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "1"
              memory = "${var.redis_memory_mb}Mi"
            }
          }

          readiness_probe {
            exec {
              command = ["redis-cli", "ping"]
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }

          volume_mount {
            name       = "redis-data"
            mount_path = "/data"
          }
        }

        volume {
          name = "redis-data"
          empty_dir {}
        }
      }
    }
  }
}

resource "kubernetes_service" "redis" {
  metadata {
    name      = "redis"
    namespace = kubernetes_namespace.mesh.metadata[0].name
  }

  spec {
    selector = {
      app = "redis"
    }

    port {
      port = 6379
    }
  }
}

# ── Elasticsearch (Optional) ──────────────────────────────────────────────

resource "kubernetes_deployment" "elasticsearch" {
  count = var.elasticsearch_enabled ? 1 : 0

  metadata {
    name      = "elasticsearch"
    namespace = kubernetes_namespace.mesh.metadata[0].name
    labels = {
      app       = "elasticsearch"
      component = "hot-search"
    }
  }

  spec {
    replicas = var.elasticsearch_replicas

    selector {
      match_labels = {
        app = "elasticsearch"
      }
    }

    template {
      metadata {
        labels = {
          app       = "elasticsearch"
          component = "hot-search"
        }
      }

      spec {
        container {
          name  = "elasticsearch"
          image = "docker.elastic.co/elasticsearch/elasticsearch:8.14.0"

          port {
            name           = "http"
            container_port = 9200
          }

          env {
            name  = "discovery.type"
            value = "single-node"
          }
          env {
            name  = "xpack.security.enabled"
            value = "false"
          }
          env {
            name  = "ES_JAVA_OPTS"
            value = "-Xms1g -Xmx1g"
          }

          resources {
            requests = {
              cpu    = "500m"
              memory = "2Gi"
            }
            limits = {
              cpu    = "2"
              memory = "4Gi"
            }
          }

          readiness_probe {
            http_get {
              path = "/_cluster/health"
              port = 9200
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }

          volume_mount {
            name       = "es-data"
            mount_path = "/usr/share/elasticsearch/data"
          }
        }

        volume {
          name = "es-data"
          empty_dir {}
        }
      }
    }
  }
}

resource "kubernetes_service" "elasticsearch" {
  count = var.elasticsearch_enabled ? 1 : 0

  metadata {
    name      = "elasticsearch"
    namespace = kubernetes_namespace.mesh.metadata[0].name
  }

  spec {
    selector = {
      app = "elasticsearch"
    }

    port {
      port = 9200
    }
  }
}

# ── Mesh Gateway Deployment ──────────────────────────────────────────────

resource "kubernetes_config_map" "mesh_config" {
  metadata {
    name      = "mesh-config"
    namespace = kubernetes_namespace.mesh.metadata[0].name
  }

  data = {
    "system.toml" = <<-EOT
      [mesh]
      qdrant_host = "qdrant.${var.namespace}.svc.cluster.local"
      qdrant_port = 6334
      qdrant_use_grpc = true
      ollama_host = "http://ollama-embed.${var.namespace}.svc.cluster.local:11434"
      ollama_model = "${var.embedding_model}"
      redis_host = "redis.${var.namespace}.svc.cluster.local"
      redis_port = 6379
      embedding_dimension = ${var.embedding_dimension}
      collections_auto_create = true
      log_level = "INFO"

      [mesh.chunking]
      default_strategy = "semantic"
      default_chunk_size = 512
      default_overlap = 64

      [mesh.search]
      default_top_k = 10
      hybrid_enabled = true
      rrf_k = 60
    EOT
  }
}

resource "kubernetes_deployment" "mesh_gateway" {
  metadata {
    name      = "mesh-gateway"
    namespace = kubernetes_namespace.mesh.metadata[0].name
    labels = {
      app       = "mesh-gateway"
      component = "api"
    }
  }

  spec {
    replicas = 2

    selector {
      match_labels = {
        app = "mesh-gateway"
      }
    }

    template {
      metadata {
        labels = {
          app       = "mesh-gateway"
          component = "api"
        }
      }

      spec {
        service_account_name = "mesh-gateway-sa"

        container {
          name  = "gateway"
          image = "magenta/mesh-gateway:0.1.0"

          port {
            name           = "http"
            container_port = 8000
          }

          env {
            name  = "MESH__QDRANT_HOST"
            value = "qdrant.${var.namespace}.svc.cluster.local"
          }
          env {
            name  = "MESH__QDRANT_PORT"
            value = "6334"
          }
          env {
            name  = "MESH__QDRANT_USE_GRPC"
            value = "true"
          }
          env {
            name  = "MESH__OLLAMA_HOST"
            value = "http://ollama-embed.${var.namespace}.svc.cluster.local:11434"
          }
          env {
            name  = "MESH__OLLAMA_MODEL"
            value = var.embedding_model
          }
          env {
            name  = "MESH__REDIS_HOST"
            value = "redis.${var.namespace}.svc.cluster.local"
          }
          env {
            name  = "MESH__REDIS_PORT"
            value = "6379"
          }
          env {
            name  = "MESH__EMBEDDING_DIMENSION"
            value = tostring(var.embedding_dimension)
          }
          env {
            name  = "MESH__COLLECTIONS_AUTO_CREATE"
            value = "true"
          }
          env {
            name  = "MESH__LOG_LEVEL"
            value = "INFO"
          }

          resources {
            requests = {
              cpu    = "500m"
              memory = "512Mi"
            }
            limits = {
              cpu    = "2"
              memory = "2Gi"
            }
          }

          readiness_probe {
            http_get {
              path = "/api/v1/mesh/health"
              port = 8000
            }
            initial_delay_seconds = 15
            period_seconds        = 10
          }

          liveness_probe {
            http_get {
              path = "/api/v1/mesh/health"
              port = 8000
            }
            initial_delay_seconds = 45
            period_seconds        = 20
          }

          volume_mount {
            name       = "mesh-config"
            mount_path = "/app/config"
            read_only  = true
          }
        }

        volume {
          name = "mesh-config"
          config_map {
            name = kubernetes_config_map.mesh_config.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "mesh_gateway" {
  metadata {
    name      = "mesh-gateway"
    namespace = kubernetes_namespace.mesh.metadata[0].name
  }

  spec {
    selector = {
      app = "mesh-gateway"
    }

    port {
      name = "http"
      port = 8000
    }
    port {
      name = "grpc"
      port = 50055
    }
  }
}

# ── Sentinel DCR (Optional) ──────────────────────────────────────────────

resource "azurerm_monitor_data_collection_rule" "automation_activity" {
  count = var.enable_sentinel_dcr && var.log_analytics_workspace_id != "" ? 1 : 0

  name                = "${var.resource_prefix}-${var.environment}-automation-activity-dcr"
  resource_group_name = var.resource_group_name
  location            = var.location

  destinations {
    log_analytics {
      workspace_resource_id = var.log_analytics_workspace_id
      name                  = "SecurityAutomationActivity_CL"
    }
  }

  data_flow {
    streams      = ["Microsoft-SecurityAutomationActivity"]
    destinations = ["SecurityAutomationActivity_CL"]
    transform_kql = "source | extend SourceSystem = tostring(SourceSystem), ActivityId = tostring(ActivityId)"
  }

  tags = var.common_tags
}

# ── Outputs ───────────────────────────────────────────────────────────────

output "namespace" {
  value = kubernetes_namespace.mesh.metadata[0].name
}

output "qdrant_service" {
  value = "${kubernetes_service.qdrant.metadata[0].name}.${var.namespace}.svc.cluster.local"
}

output "ollama_service" {
  value = "${kubernetes_service.ollama.metadata[0].name}.${var.namespace}.svc.cluster.local:11434"
}

output "redis_service" {
  value = "${kubernetes_service.redis.metadata[0].name}.${var.namespace}.svc.cluster.local"
}

output "elasticsearch_service" {
  value = var.elasticsearch_enabled ? "${kubernetes_service.elasticsearch[0].metadata[0].name}.${var.namespace}.svc.cluster.local" : ""
}

output "mesh_gateway_service" {
  value = "${kubernetes_service.mesh_gateway.metadata[0].name}.${var.namespace}.svc.cluster.local"
}
