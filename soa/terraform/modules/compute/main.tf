# Magenta SOA — Compute Module
# Provider-agnostic compute resources (VMs, scaling, networking).

terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
    aws     = { source = "hashicorp/aws" }
    google  = { source = "hashicorp/google" }
  }
}

variable "provider" {
  description = "Cloud provider name"
  type        = string
  validation {
    condition     = contains(["azure", "aws", "gcp"], var.provider)
    error_message = "Provider must be azure, aws, or gcp."
  }
}

variable "environment" { type = string }
variable "location" { type = string }
variable "resource_prefix" { type = string }
variable "vm_sku" { type = string }
variable "node_count" { type = number }
variable "tags" { type = map(string) }

# ── Azure Compute ────────────────────────────────────────────────────────

resource "azurerm_resource_group" "this" {
  count    = var.provider == "azure" ? 1 : 0
  name     = "${var.resource_prefix}-rg"
  location = var.location
  tags     = var.tags
}

resource "azurerm_kubernetes_cluster" "this" {
  count               = var.provider == "azure" ? 1 : 0
  name                = "${var.resource_prefix}-aks"
  location            = azurerm_resource_group.this[0].location
  resource_group_name = azurerm_resource_group.this[0].name
  dns_prefix          = var.resource_prefix
  tags                = var.tags

  default_node_pool {
    name       = "agents"
    node_count = var.node_count
    vm_size    = var.vm_sku
  }

  identity { type = "SystemAssigned" }
}

# ── AWS Compute ──────────────────────────────────────────────────────────

resource "aws_eks_cluster" "this" {
  count    = var.provider == "aws" ? 1 : 0
  name     = "${var.resource_prefix}-eks"
  role_arn = var.tags["iam_role_arn"]
  version  = "1.31"

  vpc_config {
    subnet_ids = var.subnet_ids
  }

  tags = var.tags
}

resource "aws_eks_node_group" "this" {
  count           = var.provider == "aws" ? 1 : 0
  cluster_name    = aws_eks_cluster.this[0].name
  node_group_name = "${var.resource_prefix}-agents"
  node_role_arn   = var.tags["node_role_arn"]
  subnet_ids      = var.subnet_ids

  scaling_config {
    desired_size = var.node_count
    min_size     = 1
    max_size     = var.node_count * 2
  }

  instance_types = [var.vm_sku]
  tags           = var.tags
}

# ── GCP Compute ──────────────────────────────────────────────────────────

resource "google_container_cluster" "this" {
  count              = var.provider == "gcp" ? 1 : 0
  name               = "${var.resource_prefix}-gke"
  location           = var.location
  initial_node_count = var.node_count

  node_config {
    machine_type = var.vm_sku
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    labels       = var.tags
  }

  deletion_protection = false
}

# ── Outputs ──────────────────────────────────────────────────────────────

output "cluster_endpoint" {
  value = try(
    azurerm_kubernetes_cluster.this[0].kube_config.0.host,
    aws_eks_cluster.this[0].endpoint,
    google_container_cluster.this[0].endpoint,
    null
  )
}

output "pool_id" {
  value = try(
    azurerm_kubernetes_cluster.this[0].id,
    aws_eks_node_group.this[0].id,
    google_container_cluster.this[0].id,
    null
  )
}

output "node_count" {
  value = var.node_count
}
