# Magenta SOA — Multi-Cloud Provider Configuration
# Each provider is conditionally enabled via feature flags (see variables.tf).

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
