# Magenta SOA — Multi-Cloud Terraform Root Module
# Unified IaC across Azure, AWS, GCP, and private cloud (vSphere).

terraform {
  required_version = ">= 1.8.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    vsphere = {
      source  = "hashicorp/vsphere"
      version = "~> 2.8"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.32"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.15"
    }
  }
  backend "azurerm" {}
}

# ── Provider configs in providers.tf ─────────────────────────────────────

# ── Multi-Cloud Compute ───────────────────────────────────────────────────

module "compute_azure" {
  source   = "./modules/compute"
  count    = var.enable_azure ? 1 : 0
  provider = "azure"

  environment     = var.environment
  location        = var.azure_location
  resource_prefix = "${var.resource_prefix}-azure"
  vm_sku          = var.compute_vm_sku
  node_count      = var.compute_node_count

  tags = merge(var.common_tags, { provider = "azure" })
}

module "compute_aws" {
  source   = "./modules/compute"
  count    = var.enable_aws ? 1 : 0
  provider = "aws"

  environment     = var.environment
  location        = var.aws_region
  resource_prefix = "${var.resource_prefix}-aws"
  vm_sku          = var.compute_vm_sku
  node_count      = var.compute_node_count

  tags = merge(var.common_tags, { provider = "aws" })
}

module "compute_gcp" {
  source   = "./modules/compute"
  count    = var.enable_gcp ? 1 : 0
  provider = "gcp"

  environment     = var.environment
  location        = var.gcp_region
  resource_prefix = "${var.resource_prefix}-gcp"
  vm_sku          = var.compute_vm_sku
  node_count      = var.compute_node_count

  tags = merge(var.common_tags, { provider = "gcp" })
}

# ── Kubernetes Clusters ──────────────────────────────────────────────────

module "kubernetes_azure" {
  source   = "./modules/kubernetes"
  count    = var.enable_azure && var.enable_kubernetes ? 1 : 0
  provider = "azure"

  environment     = var.environment
  location        = var.azure_location
  cluster_name    = "${var.resource_prefix}-aks"
  node_pool_sku   = var.k8s_node_pool_sku
  node_count      = var.k8s_node_count
  service_cidr    = var.k8s_service_cidr

  tags = merge(var.common_tags, { provider = "azure", service = "aks" })
}

module "kubernetes_aws" {
  source   = "./modules/kubernetes"
  count    = var.enable_aws && var.enable_kubernetes ? 1 : 0
  provider = "aws"

  environment     = var.environment
  location        = var.aws_region
  cluster_name    = "${var.resource_prefix}-eks"
  node_pool_sku   = var.k8s_node_pool_sku
  node_count      = var.k8s_node_count
  service_cidr    = var.k8s_service_cidr

  tags = merge(var.common_tags, { provider = "aws", service = "eks" })
}

module "kubernetes_gcp" {
  source   = "./modules/kubernetes"
  count    = var.enable_gcp && var.enable_kubernetes ? 1 : 0
  provider = "gcp"

  environment     = var.environment
  location        = var.gcp_region
  cluster_name    = "${var.resource_prefix}-gke"
  node_pool_sku   = var.k8s_node_pool_sku
  node_count      = var.k8s_node_count
  service_cidr    = var.k8s_service_cidr

  tags = merge(var.common_tags, { provider = "gcp", service = "gke" })
}

# ── Outputs ──────────────────────────────────────────────────────────────

output "cluster_endpoints" {
  value = {
    azure = try(module.kubernetes_azure[0].cluster_endpoint, null)
    aws   = try(module.kubernetes_aws[0].cluster_endpoint, null)
    gcp   = try(module.kubernetes_gcp[0].cluster_endpoint, null)
  }
}

output "compute_pools" {
  value = {
    azure = try(module.compute_azure[0].pool_id, null)
    aws   = try(module.compute_aws[0].pool_id, null)
    gcp   = try(module.compute_gcp[0].pool_id, null)
  }
}

output "cost_tags" {
  value = {
    environment = var.environment
    project     = var.resource_prefix
    managed_by  = "magenta-agent-ops"
  }
}
