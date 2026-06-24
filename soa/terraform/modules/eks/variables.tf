# EKS Module Variables

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for EKS (public + private)"
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security group IDs"
  type        = list(string)
  default     = []
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.31"
}

variable "system_node_sku" {
  description = "VM SKU for system node group"
  type        = string
  default     = "t3.medium"
}

variable "system_node_count" {
  description = "Desired node count for system pool"
  type        = number
  default     = 2
}

variable "os_disk_size_gb" {
  description = "OS disk size in GB"
  type        = number
  default     = 100
}

variable "service_cidr" {
  description = "Service CIDR for Kubernetes"
  type        = string
  default     = null
}

variable "private_cluster" {
  description = "Enable private cluster (private endpoint)"
  type        = bool
  default     = false
}

variable "enable_auto_scaling" {
  description = "Enable cluster autoscaler"
  type        = bool
  default     = true
}

variable "min_node_count" {
  description = "Minimum node count with autoscaler"
  type        = number
  default     = 1
}

variable "max_node_count" {
  description = "Maximum node count with autoscaler"
  type        = number
  default     = 6
}

variable "enable_audit_logging" {
  description = "Enable EKS audit logging"
  type        = bool
  default     = true
}

variable "vpc_cni_version" {
  description = "VPC CNI addon version"
  type        = string
  default     = "v1.18.3-eksbuild.3"
}

variable "coredns_version" {
  description = "CoreDNS addon version"
  type        = string
  default     = "v1.11.3-eksbuild.1"
}

variable "kube_proxy_version" {
  description = "kube-proxy addon version"
  type        = string
  default     = "v1.31.0-eksbuild.3"
}

variable "user_node_groups" {
  description = "User node group definitions"
  type = map(object({
    vm_size         = string
    node_count      = optional(number, 2)
    os_disk_size_gb = optional(number, 100)
    min_count       = optional(number, 1)
    node_labels     = optional(map(string), {})
    taints = optional(list(object({
      key    = string
      value  = string
      effect = string
    })), [])
  }))
  default = {}
}

variable "enable_gpu_operator" {
  description = "Enable NVIDIA GPU Operator for GPU node groups"
  type        = bool
  default     = false
}

variable "gpu_driver_version" {
  description = "NVIDIA driver version for GPU nodes"
  type        = string
  default     = "latest"
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
