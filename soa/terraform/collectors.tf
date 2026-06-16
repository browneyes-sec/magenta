# Collector Infrastructure Modules
# Azure DCR, AWS CloudTrail, GCP Logging, Ingest Gateway
# Each module is independently enabled via feature flags.

# ── Azure Data Collection Rule (DCR) ──────────────────────────────────────

module "azure_dcr" {
  source = "./modules/collectors/azure-dcr"
  count  = var.enable_azure && var.enable_azure_dcr ? 1 : 0

  environment             = var.environment
  resource_prefix         = var.resource_prefix
  resource_group_name     = "${var.resource_prefix}-monitoring"
  location                = var.azure_location
  common_tags             = var.common_tags
  eventhub_id             = module.capture[0].eventhub_id
  eventhub_namespace_id   = module.capture[0].eventhub_namespace_id
  eventhub_topic_name     = "raw-logs"
  log_analytics_workspace_id = var.azure_log_analytics_workspace_id
  key_vault_ids           = var.azure_key_vault_ids
  aks_cluster_ids         = try([module.aks[0].cluster_id], [])
}

# ── AWS CloudTrail → S3 + EventBridge ────────────────────────────────────

module "aws_cloudtrail" {
  source = "./modules/collectors/aws-cloudtrail"
  count  = var.enable_aws && var.enable_aws_cloudtrail ? 1 : 0

  environment           = var.environment
  resource_prefix       = var.resource_prefix
  common_tags           = var.common_tags
  kms_key_id            = var.aws_kms_key_id
  enable_partner_eventhub = var.enable_aws_eventhub_partner
  partner_eventhub_arn  = var.aws_partner_eventhub_arn
  collector_role_arn    = var.aws_collector_role_arn
}

# ── GCP Cloud Logging → Pub/Sub ──────────────────────────────────────────

module "gcp_logging" {
  source = "./modules/collectors/gcp-logging"
  count  = var.enable_gcp && var.enable_gcp_logging ? 1 : 0

  environment                  = var.environment
  resource_prefix              = var.resource_prefix
  project_id                   = var.gcp_project_id
  region                       = var.gcp_region
  common_tags                  = var.common_tags
  enable_eventhub_forwarder    = var.enable_gcp_eventhub_forwarder
  forwarder_image              = var.gcp_forwarder_image
  eventhub_namespace           = module.capture[0].eventhub_namespace
  eventhub_topic               = "raw-logs"
  forwarder_service_account    = var.gcp_forwarder_service_account
  collector_service_account    = var.gcp_collector_service_account
}

# ── Ingest Gateway (Application Gateway + WAF + mTLS) ────────────────────

module "ingest_gateway" {
  source = "./modules/collectors/ingest-gateway"
  count  = var.enable_ingest_gateway ? 1 : 0

  environment                 = var.environment
  resource_prefix             = var.resource_prefix
  resource_group_name         = "${var.resource_prefix}-network"
  location                    = var.azure_location
  common_tags                 = var.common_tags
  gateway_subnet_id           = try(module.network_hub[0].gateway_subnet_id, var.gateway_subnet_id)
  gateway_capacity            = var.ingest_gateway_capacity
  ingest_api_fqdns            = var.ingest_api_fqdns
  dns_zone_name               = var.dns_zone_name
  dns_zone_resource_group     = var.dns_zone_resource_group
  ssl_certificate_data        = var.ingest_gateway_ssl_cert_data
  ssl_certificate_password    = var.ingest_gateway_ssl_cert_password
  client_ca_certificate_data  = var.ingest_gateway_client_ca_data
  client_ca_issuer_dn         = var.ingest_gateway_client_ca_issuer_dn
  key_vault_id                = try(module.network_hub[0].key_vault_id, var.key_vault_id)
  log_analytics_workspace_id  = var.azure_log_analytics_workspace_id
}
