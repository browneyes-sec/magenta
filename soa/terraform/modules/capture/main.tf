# Event Hubs Capture → ADLS Gen2 Module
# Archives raw-logs, raw-alerts, enriched-alerts, enriched-events, audit,
# and dead-letter topics to Azure Data Lake Storage Gen2 as Parquet.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

# ── Storage Account (ADLS Gen2) ──────────────────────────────────────────

resource "azurerm_storage_account" "lake" {
  name                     = "${var.resource_prefix}${var.environment}lake"
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  is_hns_enabled           = true
  min_tls_version          = "TLS1_2"

  blob_properties {
    versioning_enabled = true
  }

  tags = var.common_tags
}

resource "azurerm_storage_container" "lake" {
  for_each             = toset(var.capture_topics)
  name                 = each.value
  storage_account_name = azurerm_storage_account.lake.name
  container_access_type = "private"
}

# ── Event Hubs Namespace ─────────────────────────────────────────────────

resource "azurerm_eventhub_namespace" "bus" {
  name                = "${var.resource_prefix}-${var.environment}-agent-bus"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = var.eventhub_sku
  capacity            = var.eventhub_capacity
  auto_inflate_enabled = var.eventhub_sku == "Standard"
  maximum_throughput_units = var.eventhub_sku == "Standard" ? var.max_throughput_units : null

  identity {
    type = "SystemAssigned"
  }

  tags = var.common_tags
}

# ── Event Hubs Topics ────────────────────────────────────────────────────

resource "azurerm_eventhub" "topics" {
  for_each          = { for t in var.capture_topics : t => t }
  name              = each.value
  namespace_name    = azurerm_eventhub_namespace.bus.name
  resource_group_name = var.resource_group_name
  partition_count   = var.topic_partitions[each.value]
  message_retention = var.topic_retention_days[each.value]
}

# ── Capture Descriptions (ADLS sink) ─────────────────────────────────────

resource "azurerm_eventhub_namespace_capture_description" "capture" {
  for_each              = toset(var.capture_topics)
  namespace_id          = azurerm_eventhub_namespace.bus.id
  eventhub_id           = azurerm_eventhub.topics[each.value].id
  archive_name_format   = "{Namespace}/{EventHub}/{PartitionId}/{Year}/{Month}/{Day}/{Hour}/{Minute}/{Second}.parquet"
  skip_empty_archives   = false

  destination {
    name                = "EventHubCapture.AzureBlobD2"
    archive_name_format = "{Namespace}/{EventHub}/{PartitionId}/{Year}/{Month}/{Day}/{Hour}/{Minute}/{Second}.parquet"
    blob_container_name = each.value
    storage_account_id  = azurerm_storage_account.lake.id
  }
}

# ── RBAC: Event Hubs → Storage ──────────────────────────────────────────

resource "azurerm_role_assignment" "eventhub_to_storage" {
  for_each             = toset(var.capture_topics)
  scope                = azurerm_storage_account.lake.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_eventhub_namespace.bus.identity[0].principal_id
}

# ── Consumer Groups ──────────────────────────────────────────────────────

locals {
  consumer_groups = flatten([
    for topic in var.capture_topics : [
      for group in var.consumer_groups : {
        topic = topic
        group = group
      }
    ]
  ])
}

resource "azurerm_eventhub_consumer_group" "groups" {
  for_each = {
    for cg in local.consumer_groups : "${cg.topic}.${cg.group}" => cg
  }
  name                = each.value.group
  namespace_name      = azurerm_eventhub_namespace.bus.name
  eventhub_name       = each.value.topic
  resource_group_name = var.resource_group_name
}
