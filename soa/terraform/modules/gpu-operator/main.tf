# NVIDIA GPU Operator Module
# Deploys the NVIDIA GPU Operator via Helm for GPU-enabled K8s clusters.
# Manages GPU drivers, device plugin, monitoring, and RuntimeClass.
#
# Usage:
#   module "gpu_operator" {
#     source = "./modules/gpu-operator"
#     cluster_name = "magenta-staging-aks"
#     provider     = "azure"
#   }

terraform {
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
  }
}

# ── Variables ──────────────────────────────────────────────────────────────

variable "cluster_name" {
  description = "Name of the K8s cluster"
  type        = string
}

variable "provider" {
  description = "Cloud provider (azure, aws, gcp, vsphere)"
  type        = string
  validation {
    condition     = contains(["azure", "aws", "gcp", "vsphere"], var.provider)
    error_message = "Provider must be azure, aws, gcp, or vsphere."
  }
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "gpu_driver_version" {
  description = "NVIDIA driver version (or 'latest')"
  type        = string
  default     = "latest"
}

variable "gpu_operator_version" {
  description = "Helm chart version for GPU Operator"
  type        = string
  default     = "24.6.0"
}

variable "enable_monitoring" {
  description = "Enable GPU monitoring with DCGM Exporter"
  type        = bool
  default     = true
}

variable "enable_gfd" {
  description = "Enable GPU Feature Discovery for automatic labeling"
  type        = bool
  default     = true
}

variable "runtime_class_name" {
  description = "RuntimeClass name for GPU workloads"
  type        = string
  default     = "nvidia"
}

variable "node_selector" {
  description = "Node selector for GPU Operator pods"
  type        = map(string)
  default     = {}
}

variable "tolerations" {
  description = "Tolerations for GPU Operator pods"
  type = list(object({
    key      = string
    operator = string
    value    = string
    effect   = string
  }))
  default = []
}

variable "tags" {
  description = "Labels to apply to resources"
  type        = map(string)
  default     = {}
}

# ── GPU Operator Helm Release ─────────────────────────────────────────────

resource "helm_release" "gpu_operator" {
  count = var.enable_gpu_operator ? 1 : 0

  name       = "gpu-operator"
  repository = "https://nvidia.github.io/gpu-operator"
  chart      = "gpu-operator"
  version    = var.gpu_operator_version
  namespace  = "gpu-operator"

  create_namespace = true

  values = [
    yamlencode({
      # ── Driver Configuration ──────────────────────────────────────────
      driver = {
        enabled = true
        version = var.gpu_driver_version
        manager = {
          env = [
            {
              name  = "PRE_INSTALL_DRIVERS"
              value = "true"
            }
          ]
        }
      }

      # ── Device Plugin ─────────────────────────────────────────────────
      devicePlugin = {
        enabled = true
        config = {
          map = {
            default = {
              "Version"                = "v1"
              "Flags"                  = {}
              "Sharing"                = {}
              "MIG"                    = {}
              "CDI"                    = {}
              "GFD"                    = {}
              "nvidiaDriverVersion"    = var.gpu_driver_version
              "nvidiaSMIPath"          = "/usr/bin/nvidia-smi"
              "nvidiaPersistencedPath" = "/usr/bin/nvidia-persistenced"
            }
          }
        }
      }

      # ── GPU Feature Discovery ─────────────────────────────────────────
      gfd = {
        enabled = var.enable_gfd
        config = {
          map = {
            default = {
              "Version"                    = "v1"
              "Flags"                      = {}
              "GFD"                        = {}
              "nvidiaDriverVersion"        = var.gpu_driver_version
              "nvidiaSMIPath"              = "/usr/bin/nvidia-smi"
              "nvidiaPersistencedPath"     = "/usr/bin/nvidia-persistenced"
            }
          }
        }
      }

      # ── Monitoring (DCGM Exporter) ────────────────────────────────────
      dcgmExporter = {
        enabled = var.enable_monitoring
        service = {
          type = "ClusterIP"
          ports = [
            {
              name       = "metrics"
              port       = 9400
              targetPort = 9400
              protocol   = "TCP"
            }
          ]
        }
      }

      # ── Toolkit ──────────────────────────────────────────────────────
      toolkit = {
        enabled = true
      }

      # ── Node Feature Discovery ────────────────────────────────────────
      nfd = {
        enabled = true
      }

      # ── Operator Configuration ────────────────────────────────────────
      operator = {
        replicaCount = var.environment == "production" ? 2 : 1
        priorityClassName = "system-cluster-critical"
        tolerations = [
          {
            key      = "nvidia.com/gpu"
            operator = "Exists"
            effect   = "NoSchedule"
          }
        ]
        nodeSelector = var.node_selector
      }
    })
  ]

  depends_on = [
    kubernetes_namespace.gpu_operator
  ]
}

# ── Namespace ──────────────────────────────────────────────────────────────

resource "kubernetes_namespace" "gpu_operator" {
  count = var.enable_gpu_operator ? 1 : 0

  metadata {
    name = "gpu-operator"

    labels = merge(var.tags, {
      "app.kubernetes.io/name"       = "gpu-operator"
      "app.kubernetes.io/managed-by" = "terraform"
    })
  }
}

# ── RuntimeClass for GPU Workloads ────────────────────────────────────────

resource "kubernetes_runtime_class_v1" "gpu" {
  count = var.enable_gpu_operator ? 1 : 0

  metadata {
    name = var.runtime_class_name

    labels = merge(var.tags, {
      "app.kubernetes.io/name"       = "nvidia-gpu"
      "app.kubernetes.io/managed-by" = "terraform"
    })
  }

  handler = "nvidia"

  overhead {
    cpu    = "100m"
    memory = "64Mi"
  }

  scheduling = {
    node_selector = {
      "nvidia.com/gpu.present" = "true"
    }
  }
}

# ── PodMonitor for GPU Metrics ────────────────────────────────────────────

resource "kubernetes_manifest" "gpu_pod_monitor" {
  count = var.enable_monitoring ? 1 : 0

  manifest = {
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "PodMonitor"
    metadata = {
      name      = "dcgm-exporter"
      namespace = "gpu-operator"
      labels    = var.tags
    }
    spec = {
      selector = {
        matchLabels = {
          "app.kubernetes.io/name" = "dcgm-exporter"
        }
      }
      namespaceSelector = {
        matchNames = ["gpu-operator"]
      }
      podMetricsEndpoints = [
        {
          port     = "metrics"
          interval = "30s"
          path     = "/metrics"
        }
      ]
    }
  }
}

# ── ServiceMonitor for GPU Metrics ────────────────────────────────────────

resource "kubernetes_manifest" "gpu_service_monitor" {
  count = var.enable_monitoring ? 1 : 0

  manifest = {
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "ServiceMonitor"
    metadata = {
      name      = "dcgm-exporter"
      namespace = "gpu-operator"
      labels    = var.tags
    }
    spec = {
      selector = {
        matchLabels = {
          "app.kubernetes.io/name" = "dcgm-exporter"
        }
      }
      namespaceSelector = {
        matchNames = ["gpu-operator"]
      }
      endpoints = [
        {
          port     = "metrics"
          interval = "30s"
          path     = "/metrics"
        }
      ]
    }
  }
}

# ── Outputs ────────────────────────────────────────────────────────────────

output "namespace" {
  value = var.enable_gpu_operator ? kubernetes_namespace.gpu_operator[0].metadata[0].name : null
}

output "runtime_class_name" {
  value = var.enable_gpu_operator ? kubernetes_runtime_class_v1.gpu[0].metadata[0].name : null
}

output "helm_release_status" {
  value = var.enable_gpu_operator ? helm_release.gpu_operator[0].status : null
}

output "monitoring_enabled" {
  value = var.enable_monitoring
}
