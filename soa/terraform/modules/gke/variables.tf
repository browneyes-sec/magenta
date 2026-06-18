# GKE Module Variables

variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
}

variable "location" {
  description = "GCP region or zone"
  type        = string
}

variable "node_locations" {
  description = "Zones for node pools"
  type        = list(string)
  default     = []
}

variable "project_id" {
  description = "GCP project ID"
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

variable "network" {
  description = "VPC network name"
  type        = string
  default     = "default"
}

variable "subnetwork" {
  description = "VPC subnetwork name"
  type        = string
  default     = "default"
}

variable "pods_range_name" {
  description = "Secondary range name for pods"
  type        = string
  default     = null
}

variable "services_range_name" {
  description = "Secondary range name for services"
  type        = string
  default     = null
}

variable "master_ipv4_cidr" {
  description = "Master IPv4 CIDR for private clusters"
  type        = string
  default     = "172.16.0.0/28"
}

variable "authorized_cidr_blocks" {
  description = "Master authorized networks"
  type = list(object({
    cidr         = string
    display_name = optional(string)
  }))
  default = []
}

variable "system_node_sku" {
  description = "Machine type for system node pool"
  type        = string
  default     = "e2-standard-4"
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
  default     = 6
}

variable "network_policy" {
  description = "Network policy provider (CALICO or none)"
  type        = string
  default     = "CALICO"
  validation {
    condition     = contains(["CALICO", "none"], var.network_policy)
    error_message = "Network policy must be CALICO or none."
  }
}

variable "release_channel" {
  description = "GKE release channel"
  type        = string
  default     = "REGULAR"
  validation {
    condition     = contains(["UNSPECIFIED", "RAPID", "REGULAR", "STABLE"], var.release_channel)
    error_message = "Release channel must be UNSPECIFIED, RAPID, REGULAR, or STABLE."
  }
}

variable "user_node_pools" {
  description = "User node pool definitions"
  type = map(object({
    vm_size         = string
    node_count      = optional(number, 2)
    os_disk_size_gb = optional(number, 100)
    disk_type       = optional(string, "pd-standard")
    min_count       = optional(number, 1)
    max_count       = optional(number, 10)
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
  description = "Labels to apply to resources"
  type        = map(string)
  default     = {}
}
