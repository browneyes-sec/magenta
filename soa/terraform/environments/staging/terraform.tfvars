# Staging Environment — Terraform Variables
# 65% Azure / 25% AWS / 10% vSphere cost allocation

environment = "staging"

# ── Feature Flags ────────────────────────────────────────────────────────

enable_azure     = true
enable_aws       = true
enable_gcp       = false
enable_vsphere   = true
enable_kubernetes = true
use_new_k8s_modules = true
enable_network_hub   = true

# ── Azure ────────────────────────────────────────────────────────────────

azure_location    = "eastus2"
azure_hub_cidr    = "10.0.0.0/16"
azure_hub_subnets = {
  gateway  = "10.0.1.0/24"
  firewall = "10.0.2.0/24"
  shared   = "10.0.3.0/24"
  aks       = "10.0.4.0/22"
}

# ── AWS ──────────────────────────────────────────────────────────────────

aws_region   = "us-east-1"
aws_hub_cidr = "10.1.0.0/16"

# ── GCP ──────────────────────────────────────────────────────────────────

gcp_project_id = ""
gcp_region     = "us-central1"
gcp_hub_cidr   = "10.2.0.0/16"

# ── vSphere ──────────────────────────────────────────────────────────────

vsphere_datacenter      = "dc-01"
vsphere_compute_cluster = "cluster-01"
vsphere_datastore       = "ds-staging"
vsphere_network         = "VM Network"
vsphere_template        = "ubuntu-24-04-template"
vsphere_vm_folder       = "/magenta/staging"
vsphere_cp_cidr         = "192.168.10.0/24"
vsphere_worker_cidr     = "192.168.11.0/24"

# ── Kubernetes ───────────────────────────────────────────────────────────

k8s_kubernetes_version = "1.30"
k8s_system_node_sku    = "Standard_D4s_v5"
k8s_system_node_count  = 2
k8s_service_cidr       = "10.96.0.0/12"
k8s_private_cluster    = false
k8s_enable_auto_scaling = true
k8s_min_node_count     = 1
k8s_max_node_count     = 6
k8s_user_node_pools = {
  agents = {
    vm_size    = "Standard_D8s_v5"
    node_count = 2
  }
  gpu = {
    vm_size    = "Standard_NC24s_v3"
    node_count = 1
    node_labels = {
      "accelerator" = "nvidia-tesla"
    }
    node_taints = ["nvidia.com/gpu=:NoSchedule"]
  }
}

# ── Budget ────────────────────────────────────────────────────────────────

budget_monthly_total    = 3000
budget_provider_amounts = {
  azure = 1500
  aws   = 500
}
budget_notification_email = "finops@magenta.local"
budget_alert_thresholds   = [50, 80, 95]

# ── Compute (Legacy) ─────────────────────────────────────────────────────

compute_vm_sku     = "Standard_D4s_v5"
compute_node_count = 3
