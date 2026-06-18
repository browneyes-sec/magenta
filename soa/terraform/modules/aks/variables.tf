# AKS Module Variables

variable "cluster_name" {
  description = "Name of the AKS cluster"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
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
  description = "VM SKU for system node pool"
  type        = string
  default     = "Standard_D4s_v5"
}

variable "system_node_count" {
  description = "Node count for system pool"
  type        = number
  default     = 2
}

variable "os_disk_size_gb" {
  description = "OS disk size in GB"
  type        = number
  default     = 100
}

variable "subnet_id" {
  description = "Subnet ID for AKS"
  type        = string
  default     = null
}

variable "service_cidr" {
  description = "Service CIDR for Kubernetes"
  type        = string
  default     = "10.96.0.0/12"
}

variable "private_cluster" {
  description = "Enable private cluster"
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
  default     = 5
}

variable "enable_aad_rbac" {
  description = "Enable Azure AD RBAC"
  type        = bool
  default     = true
}

variable "aad_admin_group_ids" {
  description = "Azure AD admin group IDs"
  type        = list(string)
  default     = []
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID for monitoring"
  type        = string
  default     = null
}

variable "enable_cost_allocation" {
  description = "Enable cost allocation labels"
  type        = bool
  default     = true
}

variable "user_node_pools" {
  description = "User node pool definitions"
  type = map(object({
    vm_size            = string
    node_count         = optional(number, 2)
    os_disk_size_gb    = optional(number, 100)
    enable_auto_scaling = optional(bool, true)
    min_count          = optional(number, 1)
    max_count          = optional(number, 10)
    node_labels        = optional(map(string), {})
    node_taints        = optional(list(string), [])
    priority           = optional(string, "Regular")
  }))
  default = {}
}

variable "enable_gpu_operator" {
  description = "Enable NVIDIA GPU Operator for GPU node pools"
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
