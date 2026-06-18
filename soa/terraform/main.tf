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

# ── Multi-Cloud Network Hub ──────────────────────────────────────────────

module "network_hub" {
  source = "./modules/network"
  count  = var.enable_network_hub ? 1 : 0

  environment = var.environment
  region      = var.azure_location

  azure_hub_cidr    = var.azure_hub_cidr
  azure_hub_subnets = var.azure_hub_subnets
  aws_hub_cidr      = var.aws_hub_cidr
  gcp_hub_cidr      = var.gcp_hub_cidr
  gcp_project_id    = var.gcp_project_id

  tags = var.common_tags
}

# ── Multi-Cloud Compute ──────────────────────────────────────────────────

# Generic compute module (legacy path)
module "compute_azure" {
  source   = "./modules/compute"
  count    = var.enable_azure && !var.use_new_k8s_modules ? 1 : 0
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
  count    = var.enable_aws && !var.use_new_k8s_modules ? 1 : 0
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
  count    = var.enable_gcp && !var.use_new_k8s_modules ? 1 : 0
  provider = "gcp"

  environment     = var.environment
  location        = var.gcp_region
  resource_prefix = "${var.resource_prefix}-gcp"
  vm_sku          = var.compute_vm_sku
  node_count      = var.compute_node_count

  tags = merge(var.common_tags, { provider = "gcp" })
}

# ── Kubernetes Clusters (Legacy) ─────────────────────────────────────────

module "kubernetes_azure" {
  source   = "./modules/kubernetes"
  count    = var.enable_azure && var.enable_kubernetes && !var.use_new_k8s_modules ? 1 : 0
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
  count    = var.enable_aws && var.enable_kubernetes && !var.use_new_k8s_modules ? 1 : 0
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
  count    = var.enable_gcp && var.enable_kubernetes && !var.use_new_k8s_modules ? 1 : 0
  provider = "gcp"

  environment     = var.environment
  location        = var.gcp_region
  cluster_name    = "${var.resource_prefix}-gke"
  node_pool_sku   = var.k8s_node_pool_sku
  node_count      = var.k8s_node_count
  service_cidr    = var.k8s_service_cidr

  tags = merge(var.common_tags, { provider = "gcp", service = "gke" })
}

# ── Per-Provider K8s Modules (New) ───────────────────────────────────────

module "aks" {
  source = "./modules/aks"
  count  = var.enable_azure && var.enable_kubernetes && var.use_new_k8s_modules ? 1 : 0

  cluster_name        = "${var.resource_prefix}-aks"
  location            = var.azure_location
  resource_group_name = "${var.resource_prefix}-aks-rg"
  environment         = var.environment
  kubernetes_version  = var.k8s_kubernetes_version
  system_node_sku     = var.k8s_system_node_sku
  system_node_count   = var.k8s_system_node_count
  service_cidr        = var.k8s_service_cidr
  private_cluster     = var.k8s_private_cluster
  enable_auto_scaling = var.k8s_enable_auto_scaling
  min_node_count      = var.k8s_min_node_count
  max_node_count      = var.k8s_max_node_count
  enable_cost_allocation = true
  user_node_pools     = var.k8s_user_node_pools
  log_analytics_workspace_id = var.azure_log_analytics_workspace_id

  tags = merge(var.common_tags, { provider = "azure", service = "aks" })
}

module "eks" {
  source = "./modules/eks"
  count  = var.enable_aws && var.enable_kubernetes && var.use_new_k8s_modules ? 1 : 0

  cluster_name       = "${var.resource_prefix}-eks"
  subnet_ids         = try(module.network_hub[0].aws_hub_vpc_id, [])
  environment        = var.environment
  kubernetes_version = var.k8s_kubernetes_version
  system_node_sku    = replace(var.k8s_system_node_sku, "/^Standard_/", "t3.")
  system_node_count  = var.k8s_system_node_count
  service_cidr       = var.k8s_service_cidr
  private_cluster    = var.k8s_private_cluster
  enable_auto_scaling = var.k8s_enable_auto_scaling
  min_node_count     = var.k8s_min_node_count
  max_node_count     = var.k8s_max_node_count
  user_node_groups   = var.k8s_user_node_pools

  tags = merge(var.common_tags, { provider = "aws", service = "eks" })
}

module "gke" {
  source = "./modules/gke"
  count  = var.enable_gcp && var.enable_kubernetes && var.use_new_k8s_modules ? 1 : 0

  cluster_name       = "${var.resource_prefix}-gke"
  location           = var.gcp_region
  project_id         = var.gcp_project_id
  environment        = var.environment
  kubernetes_version = var.k8s_kubernetes_version
  system_node_sku    = replace(var.k8s_system_node_sku, "/^Standard_/", "e2-standard-")
  system_node_count  = var.k8s_system_node_count
  private_cluster    = var.k8s_private_cluster
  enable_auto_scaling = var.k8s_enable_auto_scaling
  min_node_count     = var.k8s_min_node_count
  max_node_count     = var.k8s_max_node_count
  user_node_pools    = var.k8s_user_node_pools

  tags = merge(var.common_tags, { provider = "gcp", service = "gke" })
}

# ── GPU Operator (per-provider) ────────────────────────────────────────────

module "gpu_operator_azure" {
  source = "./modules/gpu-operator"
  count  = var.enable_azure && var.enable_kubernetes && var.enable_gpu_operator && var.use_new_k8s_modules ? 1 : 0

  cluster_name         = "${var.resource_prefix}-aks"
  provider             = "azure"
  environment          = var.environment
  gpu_driver_version   = var.gpu_driver_version
  gpu_operator_version = var.gpu_operator_version
  enable_monitoring    = var.enable_gpu_monitoring

  tags = merge(var.common_tags, { provider = "azure", service = "gpu-operator" })
}

module "gpu_operator_aws" {
  source = "./modules/gpu-operator"
  count  = var.enable_aws && var.enable_kubernetes && var.enable_gpu_operator && var.use_new_k8s_modules ? 1 : 0

  cluster_name         = "${var.resource_prefix}-eks"
  provider             = "aws"
  environment          = var.environment
  gpu_driver_version   = var.gpu_driver_version
  gpu_operator_version = var.gpu_operator_version
  enable_monitoring    = var.enable_gpu_monitoring

  tags = merge(var.common_tags, { provider = "aws", service = "gpu-operator" })
}

module "gpu_operator_gcp" {
  source = "./modules/gpu-operator"
  count  = var.enable_gcp && var.enable_kubernetes && var.enable_gpu_operator && var.use_new_k8s_modules ? 1 : 0

  cluster_name         = "${var.resource_prefix}-gke"
  provider             = "gcp"
  environment          = var.environment
  gpu_driver_version   = var.gpu_driver_version
  gpu_operator_version = var.gpu_operator_version
  enable_monitoring    = var.enable_gpu_monitoring

  tags = merge(var.common_tags, { provider = "gcp", service = "gpu-operator" })
}

# ── vSphere Private Cloud ─────────────────────────────────────────────────

module "vsphere_cluster" {
  source = "./modules/vsphere"
  count  = var.enable_vsphere ? 1 : 0

  datacenter         = var.vsphere_datacenter
  compute_cluster    = var.vsphere_compute_cluster
  datastore          = var.vsphere_datastore
  network_name       = var.vsphere_network
  template_name      = var.vsphere_template
  folder_path        = var.vsphere_vm_folder
  vm_name_prefix     = "${var.resource_prefix}-vsphere"
  control_plane_cidr = var.vsphere_cp_cidr
  worker_cidr        = var.vsphere_worker_cidr
  control_plane_count = 3
  worker_count        = var.compute_node_count
  control_plane_cpu   = 4
  worker_cpu          = 8
  control_plane_memory_mb = 16384
  worker_memory_mb        = 32768

  tags = merge(var.common_tags, { provider = "vsphere" })
}

# ── Event Hubs Capture → ADLS ─────────────────────────────────────────────

module "capture" {
  source = "./modules/capture"
  count  = var.enable_capture ? 1 : 0

  environment         = var.environment
  resource_prefix     = var.resource_prefix
  resource_group_name = "${var.resource_prefix}-data"
  location            = var.azure_location
  common_tags         = var.common_tags

  capture_topics       = var.capture_topics
  topic_partitions     = var.capture_topic_partitions
  topic_retention_days = var.capture_topic_retention_days
  eventhub_sku         = var.capture_eventhub_sku
  eventhub_capacity    = var.capture_eventhub_capacity
  consumer_groups      = var.capture_consumer_groups
}

# ── Budget Management (Azure) ──────────────────────────────────────────────

module "budget" {
  source = "./modules/budget"
  count  = var.enable_azure ? 1 : 0

  environment         = var.environment
  resource_group_name = "${var.resource_prefix}-monitoring"
  monthly_budget_total = var.budget_monthly_total
  provider_budgets    = var.budget_provider_amounts
  notification_email  = var.budget_notification_email
  webhook_url         = var.budget_webhook_url
  enable_block_threshold = var.environment == "production"
  alert_thresholds    = var.budget_alert_thresholds
  filter_tags         = var.budget_filter_tags

  tags = merge(var.common_tags, { service = "budget" })
}

# ── Collector Infrastructure ───────────────────────────────────────────────

module "collectors" {
  source = "./collectors.tf"
  count  = 1
}
