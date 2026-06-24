# Azure Kubernetes Service (AKS) Module
# Manages AKS clusters with Azure AD integration, private cluster mode,
# multiple node pools, monitoring, and cost allocation tags.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

# ── Resource Group ───────────────────────────────────────────────────────

resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

# ── AKS Cluster ──────────────────────────────────────────────────────────

resource "azurerm_kubernetes_cluster" "this" {
  name                = var.cluster_name
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  dns_prefix          = var.cluster_name
  kubernetes_version  = var.kubernetes_version
  tags                = var.tags

  sku_tier = var.environment == "production" ? "Standard" : "Free"

  default_node_pool {
    name                = "system"
    node_count          = var.system_node_count
    vm_size             = var.system_node_sku
    os_disk_size_gb     = var.os_disk_size_gb
    vnet_subnet_id      = var.subnet_id
    enable_auto_scaling = var.enable_auto_scaling
    min_count           = var.enable_auto_scaling ? var.min_node_count : null
    max_count           = var.enable_auto_scaling ? var.max_node_count : null
  }

  identity {
    type = "SystemAssigned"
  }

  dynamic "azure_active_directory_role_based_access_control" {
    for_each = var.enable_aad_rbac ? [1] : []
    content {
      managed            = true
      azure_rbac_enabled = true
      admin_group_object_ids = var.aad_admin_group_ids
    }
  }

  network_profile {
    network_plugin    = "azure"
    network_policy    = "calico"
    load_balancer_sku = "standard"
    service_cidr      = var.service_cidr
    dns_service_ip    = cidrhost(var.service_cidr, 10)
  }

  dynamic "private_cluster_enabled" {
    for_each = var.private_cluster ? [1] : []
    content {
      enabled                   = true
      private_dns_zone_id       = "System"
      private_cluster_public_fqdn_enabled = var.environment != "production"
    }
  }

  microsoft_defender {
    log_analytics_workspace_id = var.log_analytics_workspace_id
  }

  oms_agent {
    log_analytics_workspace_id = var.log_analytics_workspace_id
  }

  cost_analysis_enabled = var.enable_cost_allocation

  lifecycle {
    ignore_changes = [
      default_node_pool[0].node_count,
    ]
  }
}

# ── User Node Pools ──────────────────────────────────────────────────────

resource "azurerm_kubernetes_cluster_node_pool" "user" {
  for_each = var.user_node_pools

  name                  = each.key
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = each.value.vm_size
  node_count            = each.value.node_count
  os_disk_size_gb       = lookup(each.value, "os_disk_size_gb", var.os_disk_size_gb)
  vnet_subnet_id        = var.subnet_id
  enable_auto_scaling   = lookup(each.value, "enable_auto_scaling", var.enable_auto_scaling)
  min_count             = lookup(each.value, "min_count", null)
  max_count             = lookup(each.value, "max_count", null)
  node_labels           = lookup(each.value, "node_labels", {})
  node_taints           = lookup(each.value, "node_taints", [])
  priority              = lookup(each.value, "priority", "Regular")
  tags                  = var.tags

  lifecycle {
    ignore_changes = [
      node_count,
    ]
  }
}

# ── Outputs ──────────────────────────────────────────────────────────────

output "cluster_id" {
  value = azurerm_kubernetes_cluster.this.id
}

output "cluster_name" {
  value = azurerm_kubernetes_cluster.this.name
}

output "cluster_endpoint" {
  value = azurerm_kubernetes_cluster.this.kube_config[0].host
}

output "kube_config_raw" {
  value     = azurerm_kubernetes_cluster.this.kube_config_raw
  sensitive = true
}

output "node_resource_group" {
  value = azurerm_kubernetes_cluster.this.node_resource_group
}

output "identity_principal_id" {
  value = azurerm_kubernetes_cluster.this.identity[0].principal_id
}
