# GPU Operator Module Variables

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

variable "enable_gpu_operator" {
  description = "Enable GPU Operator deployment"
  type        = bool
  default     = true
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
