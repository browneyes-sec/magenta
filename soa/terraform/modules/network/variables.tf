# Network Module Variables

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "region" {
  description = "Primary region for network resources"
  type        = string
}

variable "spoke_vnets" {
  description = "Map of spoke VNet IDs for Azure peering"
  type        = map(string)
  default     = {}
}

variable "azure_hub_cidr" {
  description = "Azure hub VNet CIDR"
  type        = string
  default     = "10.0.0.0/16"
}

variable "azure_hub_subnets" {
  description = "Azure hub subnet name-to-CIDR map"
  type        = map(string)
  default = {
    "gateway"  = "10.0.1.0/24"
    "firewall" = "10.0.2.0/24"
    "shared"   = "10.0.3.0/24"
  }
}

variable "aws_hub_cidr" {
  description = "AWS hub VPC CIDR"
  type        = string
  default     = "10.1.0.0/16"
}

variable "aws_hub_subnet_cidrs" {
  description = "AWS hub subnet CIDRs"
  type        = list(string)
  default     = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
}

variable "gcp_hub_cidr" {
  description = "GCP hub subnet CIDR"
  type        = string
  default     = "10.2.0.0/16"
}

variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
