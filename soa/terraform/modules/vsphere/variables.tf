# vSphere Module Variables

variable "datacenter" {
  description = "vSphere datacenter name"
  type        = string
}

variable "compute_cluster" {
  description = "vSphere compute cluster name"
  type        = string
}

variable "datastore" {
  description = "vSphere datastore name"
  type        = string
}

variable "network_name" {
  description = "vSphere port group or network name"
  type        = string
}

variable "template_name" {
  description = "VM template name for cloning"
  type        = string
}

variable "resource_pool" {
  description = "Resource pool name (defaults to cluster root)"
  type        = string
  default     = null
}

variable "folder_path" {
  description = "VM folder path"
  type        = string
}

variable "vm_name_prefix" {
  description = "Prefix for VM names"
  type        = string
  default     = "magenta"
}

variable "domain" {
  description = "DNS domain for VMs"
  type        = string
  default     = "magenta.internal"
}

variable "dns_servers" {
  description = "DNS server list"
  type        = list(string)
  default     = ["8.8.8.8", "1.1.1.1"]
}

variable "control_plane_count" {
  description = "Number of control plane nodes"
  type        = number
  default     = 3
}

variable "control_plane_cpu" {
  description = "CPUs per control plane node"
  type        = number
  default     = 4
}

variable "control_plane_memory_mb" {
  description = "Memory in MB per control plane node"
  type        = number
  default     = 16384
}

variable "control_plane_disk_gb" {
  description = "Disk size in GB per control plane node"
  type        = number
  default     = 100
}

variable "control_plane_cidr" {
  description = "CIDR for control plane static IPs"
  type        = string
}

variable "worker_count" {
  description = "Number of worker nodes"
  type        = number
  default     = 3
}

variable "worker_cpu" {
  description = "CPUs per worker node"
  type        = number
  default     = 8
}

variable "worker_memory_mb" {
  description = "Memory in MB per worker node"
  type        = number
  default     = 32768
}

variable "worker_disk_gb" {
  description = "Disk size in GB per worker node"
  type        = number
  default     = 200
}

variable "worker_cidr" {
  description = "CIDR for worker static IPs"
  type        = string
}

variable "netmask" {
  description = "Subnet netmask (e.g. 24)"
  type        = number
  default     = 24
}

variable "ip_offset" {
  description = "Starting IP offset within CIDR"
  type        = number
  default     = 10
}

variable "disk_eagerly_scrub" {
  description = "Enable eager scrubbing for disks"
  type        = bool
  default     = false
}

variable "disk_thin_provision" {
  description = "Use thin provisioning"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to VMs"
  type        = map(string)
  default     = {}
}
