# Dev Environment — Terraform Variables
# Single-provider (Azure) for local development and testing.
# Minikube can be used instead of AKS for local dev.

environment = "dev"

enable_azure    = true
enable_aws      = false
enable_gcp      = false
enable_vsphere  = false
enable_kubernetes = true

resource_prefix = "magenta-dev"
azure_location  = "eastus2"

compute_vm_sku     = "Standard_D2s_v5"
compute_node_count = 1

k8s_node_pool_sku = "Standard_D4s_v5"
k8s_node_count    = 1
k8s_service_cidr  = "10.96.0.0/12"

common_tags = {
  project     = "magenta"
  component   = "asoar"
  managed-by  = "terraform"
  cost-center = "security-operations-dev"
  environment = "dev"
}
