# Google Kubernetes Engine (GKE) Module
# Manages GKE clusters with workload identity, VPC-native networking,
# shielded nodes, and cost allocation labels.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# ── GKE Cluster ──────────────────────────────────────────────────────────

resource "google_service_account" "gke" {
  account_id = "${replace(var.cluster_name, "-", "")}-sa"
  display_name = "${var.cluster_name} GKE SA"
}

resource "google_container_cluster" "this" {
  name                     = var.cluster_name
  location                 = var.location
  node_locations           = var.node_locations
  min_master_version       = var.kubernetes_version
  deletion_protection      = var.environment == "production"
  network                  = var.network
  subnetwork               = var.subnetwork
  private_ip_google_access = var.private_cluster
  labels                   = var.tags

  dynamic "master_authorized_networks_config" {
    for_each = var.private_cluster ? [] : [1]
    content {
      dynamic "cidr_blocks" {
        for_each = var.authorized_cidr_blocks
        content {
          cidr_block   = cidr_blocks.value.cidr
          display_name = lookup(cidr_blocks.value, "display_name", null)
        }
      }
    }
  }

  dynamic "private_cluster_config" {
    for_each = var.private_cluster ? [1] : []
    content {
      enable_private_endpoint = var.environment == "production"
      enable_private_nodes    = true
      master_ipv4_cidr_block  = var.master_ipv4_cidr
    }
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name
    services_secondary_range_name = var.services_range_name
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  addons_config {
    http_load_balancing        = { disabled = false }
    horizontal_pod_autoscaling = { disabled = false }
    network_policy_config      = { disabled = var.network_policy == "CALICO" ? false : true }
    gce_persistent_disk_csi_driver_config = { enabled = true }
  }

  dynamic "network_policy" {
    for_each = var.network_policy == "CALICO" ? [1] : []
    content {
      enabled  = true
      provider = "CALICO"
    }
  }

  release_channel {
    channel = var.release_channel
  }

  maintenance_policy {
    recurring_window {
      start_time = "03:00"
      end_time   = "05:00"
      recurrence = "FREQ=WEEKLY;BYDAY=SU"
    }
  }

  lifecycle {
    ignore_changes = [
      node_pool,
      initial_node_count,
    ]
  }
}

# ── Default Node Pool ────────────────────────────────────────────────────

resource "google_container_node_pool" "default" {
  name     = "${var.cluster_name}-system"
  cluster  = google_container_cluster.this.name
  location = var.location
  version  = var.kubernetes_version

  initial_node_count = var.system_node_count

  autoscaling {
    min_node_count = var.enable_auto_scaling ? var.min_node_count : var.system_node_count
    max_node_count = var.enable_auto_scaling ? var.max_node_count : var.system_node_count
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type    = var.system_node_sku
    disk_size_gb    = var.os_disk_size_gb
    disk_type       = "pd-standard"
    service_account = google_service_account.gke.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = var.tags
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }

  lifecycle {
    ignore_changes = [
      initial_node_count,
    ]
  }
}

# ── User Node Pools ──────────────────────────────────────────────────────

resource "google_container_node_pool" "user" {
  for_each = var.user_node_pools

  name     = "${var.cluster_name}-${each.key}"
  cluster  = google_container_cluster.this.name
  location = var.location
  version  = var.kubernetes_version

  initial_node_count = each.value.node_count

  autoscaling {
    min_node_count = lookup(each.value, "min_count", each.value.node_count)
    max_node_count = lookup(each.value, "max_count", each.value.node_count * 2)
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  dynamic "node_config" {
    content {
      machine_type    = each.value.vm_size
      disk_size_gb    = lookup(each.value, "os_disk_size_gb", var.os_disk_size_gb)
      disk_type       = lookup(each.value, "disk_type", "pd-standard")
      service_account = google_service_account.gke.email
      oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
      labels          = merge(var.tags, lookup(each.value, "node_labels", {}))
      dynamic "taint" {
        for_each = lookup(each.value, "taints", [])
        content {
          key    = taint.value.key
          value  = taint.value.value
          effect = taint.value.effect
        }
      }
      shielded_instance_config {
        enable_secure_boot          = true
        enable_integrity_monitoring = true
      }
      workload_metadata_config {
        mode = "GKE_METADATA"
      }
    }
  }

  lifecycle {
    ignore_changes = [
      initial_node_count,
    ]
  }
}

# ── Outputs ──────────────────────────────────────────────────────────────

output "cluster_id" {
  value = google_container_cluster.this.id
}

output "cluster_name" {
  value = google_container_cluster.this.name
}

output "cluster_endpoint" {
  value = google_container_cluster.this.endpoint
}

output "cluster_ca_certificate" {
  value     = base64decode(google_container_cluster.this.master_auth[0].cluster_ca_certificate)
  sensitive = true
}

output "workload_identity_pool" {
  value = google_container_cluster.this.workload_identity_config[0].workload_pool
}

output "service_account_email" {
  value = google_service_account.gke.email
}
