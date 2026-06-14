# Production Environment — Terraform Variables
# 65% Azure / 25% AWS / 10% vSphere cost allocation
# Production-grade: private clusters, auto-scaling, HA config

environment = "production"

# ── Feature Flags ────────────────────────────────────────────────────────

enable_azure           = true
enable_aws             = true
enable_gcp             = false
enable_vsphere         = true
enable_kubernetes      = true
use_new_k8s_modules    = true
enable_network_hub     = true

# ── Azure ────────────────────────────────────────────────────────────────

azure_location    = "eastus2"
azure_hub_cidr    = "10.0.0.0/16"
azure_hub_subnets = {
  gateway    = "10.0.1.0/24"
  firewall   = "10.0.2.0/24"
  shared     = "10.0.3.0/24"
  aks        = "10.0.4.0/22"
  private    = "10.0.8.0/21"
}

# ── AWS ──────────────────────────────────────────────────────────────────

aws_region   = "us-east-1"
aws_hub_cidr = "10.1.0.0/16"
aws_role_arn = "arn:aws:iam::123456789012:role/magenta-terraform-prod"

# ── GCP ──────────────────────────────────────────────────────────────────

gcp_project_id = ""
gcp_region     = "us-central1"
gcp_hub_cidr   = "10.2.0.0/16"

# ── vSphere ──────────────────────────────────────────────────────────────

vsphere_datacenter      = "dc-01"
vsphere_compute_cluster = "cluster-01"
vsphere_datastore       = "ds-production"
vsphere_network         = "Magenta-Prod"
vsphere_template        = "ubuntu-24-04-hardened-template"
vsphere_vm_folder       = "/magenta/production"
vsphere_cp_cidr         = "192.168.20.0/24"
vsphere_worker_cidr     = "192.168.21.0/24"

# ── Kubernetes ───────────────────────────────────────────────────────────

k8s_kubernetes_version = "1.31"
k8s_system_node_sku    = "Standard_D8s_v5"
k8s_system_node_count  = 3
k8s_service_cidr       = "10.96.0.0/12"
k8s_private_cluster    = true
k8s_enable_auto_scaling = true
k8s_min_node_count     = 3
k8s_max_node_count     = 10
k8s_user_node_pools = {
  agents = {
    vm_size    = "Standard_D8s_v5"
    node_count = 3
  }
  memory-intensive = {
    vm_size    = "Standard_E16s_v5"
    node_count = 2
    node_labels = {
      "workload" = "memory"
    }
    node_taints = ["memory-intensive=true:NoSchedule"]
  }
  gpu = {
    vm_size      = "Standard_NC48ads_A100_v4"
    node_count   = 1
    node_labels  = { "accelerator" = "nvidia-a100" }
    node_taints  = ["nvidia.com/gpu=:NoSchedule"]
  }
}

# ── Budget ────────────────────────────────────────────────────────────────

budget_monthly_total    = 5000
budget_provider_amounts = {
  azure = 3200
  aws   = 1250
  gcp   = 300
  vsphere = 250
}
budget_notification_email = "finops@magenta.local"
budget_webhook_url        = "https://hooks.slack.com/services/T00/B00/xxxx"
budget_alert_thresholds   = [60, 80, 90]
budget_filter_tags = {
  project     = ["magenta"]
  environment = ["production"]
}

# ── Compute (Legacy) ─────────────────────────────────────────────────────

compute_vm_sku     = "Standard_D8s_v5"
compute_node_count = 5

# ── Tags ─────────────────────────────────────────────────────────────────

common_tags = {
  project     = "magenta"
  component   = "asoar"
  managed-by  = "terraform"
  cost-center = "security-operations"
  environment = "production"
  data-classification = "il5"
}
