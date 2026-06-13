# Magenta SOA — Multi-Cloud Provider Configuration
# Each provider is conditionally enabled via environment variables.

variable "enable_azure" {
  description = "Enable Azure provider"
  type        = bool
  default     = true
}

variable "enable_aws" {
  description = "Enable AWS provider"
  type        = bool
  default     = false
}

variable "enable_gcp" {
  description = "Enable GCP provider"
  type        = bool
  default     = false
}

variable "enable_vsphere" {
  description = "Enable vSphere (private cloud) provider"
  type        = bool
  default     = false
}

variable "enable_kubernetes" {
  description = "Provision managed Kubernetes clusters"
  type        = bool
  default     = true
}

# ── Azure Provider ───────────────────────────────────────────────────────

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
  subscription_id = var.azure_subscription_id
  use_oidc        = true
}

# ── AWS Provider ─────────────────────────────────────────────────────────

provider "aws" {
  region = var.aws_region
  assume_role {
    role_arn = var.aws_role_arn
  }
  default_tags {
    tags = var.common_tags
  }
}

# ── GCP Provider ─────────────────────────────────────────────────────────

provider "google" {
  project     = var.gcp_project_id
  region      = var.gcp_region
  impersonate_service_account = var.gcp_impersonate_sa
}

# ── vSphere Provider (Private Cloud) ─────────────────────────────────────

provider "vsphere" {
  user                 = var.vsphere_user
  password             = var.vsphere_password
  vsphere_server       = var.vsphere_server
  allow_unverified_ssl = var.environment != "production"
}

# ── Variables ────────────────────────────────────────────────────────────

variable "environment" {
  description = "Deployment environment"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "resource_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "magenta"
}

variable "common_tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default = {
    project     = "magenta"
    component   = "asoar"
    managed-by  = "terraform"
    cost-center = "security-operations"
  }
}

variable "azure_subscription_id" {
  description = "Azure subscription ID"
  type        = string
  sensitive   = true
}

variable "azure_location" {
  description = "Azure region"
  type        = string
  default     = "eastus2"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_role_arn" {
  description = "AWS IAM role ARN for Terraform"
  type        = string
  default     = ""
}

variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
  default     = ""
}

variable "gcp_region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "gcp_impersonate_sa" {
  description = "GCP service account for impersonation"
  type        = string
  default     = ""
}

variable "vsphere_user" {
  description = "vSphere username"
  type        = string
  default     = ""
}

variable "vsphere_password" {
  description = "vSphere password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "vsphere_server" {
  description = "vSphere server FQDN"
  type        = string
  default     = ""
}

variable "compute_vm_sku" {
  description = "VM SKU for compute nodes"
  type        = string
  default     = "Standard_D4s_v5"
}

variable "compute_node_count" {
  description = "Number of compute nodes per provider"
  type        = number
  default     = 3
}

variable "k8s_node_pool_sku" {
  description = "Node pool VM SKU for Kubernetes"
  type        = string
  default     = "Standard_D4s_v5"
}

variable "k8s_node_count" {
  description = "Number of K8s nodes per cluster"
  type        = number
  default     = 3
}

variable "k8s_service_cidr" {
  description = "Service CIDR for Kubernetes"
  type        = string
  default     = "10.96.0.0/12"
}
