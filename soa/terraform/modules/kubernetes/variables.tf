# Kubernetes Module Variables

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.31"
}

variable "node_disk_size_gb" {
  description = "Node disk size in GB"
  type        = number
  default     = 100
}

variable "enable_autoscaling" {
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

variable "private_cluster" {
  description = "Deploy private cluster"
  type        = bool
  default     = false
}

variable "enable_cost_allocation" {
  description = "Enable K8s cost allocation labels"
  type        = bool
  default     = true
}
