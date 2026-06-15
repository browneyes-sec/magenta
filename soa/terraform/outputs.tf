# Root Module Outputs

output "cluster_endpoints" {
  description = "Kubernetes cluster endpoints by provider"
  value = {
    azure = try(module.kubernetes_azure[0].cluster_endpoint, module.aks[0].cluster_endpoint, null)
    aws   = try(module.kubernetes_aws[0].cluster_endpoint, module.eks[0].cluster_endpoint, null)
    gcp   = try(module.kubernetes_gcp[0].cluster_endpoint, module.gke[0].cluster_endpoint, null)
  }
}

output "compute_pools" {
  description = "Compute pool IDs by provider"
  value = {
    azure = try(module.compute_azure[0].pool_id, null)
    aws   = try(module.compute_aws[0].pool_id, null)
    gcp   = try(module.compute_gcp[0].pool_id, null)
  }
}

output "network_hub" {
  description = "Multi-cloud network hub IDs"
  value = try({
    azure_vnet_id        = module.network_hub[0].azure_hub_vnet_id
    azure_rg             = module.network_hub[0].azure_resource_group
    aws_vpc_id           = module.network_hub[0].aws_hub_vpc_id
    aws_transit_gateway  = module.network_hub[0].aws_transit_gateway_id
    gcp_network_id       = module.network_hub[0].gcp_hub_network_id
    gcp_subnet_id        = module.network_hub[0].gcp_hub_subnet_id
  }, null)
}

output "cost_tags" {
  description = "Cost allocation tags"
  value = {
    environment = var.environment
    project     = var.resource_prefix
    managed_by  = "magenta-agent-ops"
  }
}

output "vsphere_vms" {
  description = "vSphere VM details"
  value = try({
    control_plane_ips = module.vsphere_cluster[0].control_plane_ips
    worker_ips        = module.vsphere_cluster[0].worker_ips
    datacenter        = module.vsphere_cluster[0].datacenter
  }, null)
}

output "capture" {
  description = "Event Hubs Capture → ADLS Gen2 details"
  value = try({
    storage_account      = module.capture[0].storage_account_name
    eventhub_namespace   = module.capture[0].eventhub_namespace_name
    topic_names          = module.capture[0].topic_names
    lake_containers      = module.capture[0].lake_containers
    consumer_group_count = length(module.capture[0].consumer_groups)
  }, null)
}

output "budget" {
  description = "Budget configuration summary"
  value = try({
    action_group_id  = module.budget[0].action_group_id
    overall_budget   = module.budget[0].overall_budget_id
    provider_budgets = module.budget[0].provider_budget_ids
    monthly_limit    = module.budget[0].monthly_limit
  }, null)
}
