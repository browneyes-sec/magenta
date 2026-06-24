# Capture Module Outputs

output "storage_account_id" {
  description = "ADLS Gen2 storage account ID"
  value       = azurerm_storage_account.lake.id
}

output "storage_account_name" {
  description = "ADLS Gen2 storage account name"
  value       = azurerm_storage_account.lake.name
}

output "eventhub_namespace_id" {
  description = "Event Hubs namespace ID"
  value       = azurerm_eventhub_namespace.bus.id
}

output "eventhub_namespace_name" {
  description = "Event Hubs namespace name"
  value       = azurerm_eventhub_namespace.bus.name
}

output "eventhub_namespace_connection_string" {
  description = "Event Hubs connection string (sensitive)"
  value       = azurerm_eventhub_namespace.bus.default_primary_connection_string
  sensitive   = true
}

output "topic_names" {
  description = "Map of created topic names"
  value = {
    for k, v in azurerm_eventhub.topics : k => v.name
  }
}

output "lake_containers" {
  description = "ADLS containers created for capture"
  value = {
    for k, v in azurerm_storage_container.lake : k => v.name
  }
}

output "consumer_groups" {
  description = "Consumer group IDs"
  value = {
    for k, v in azurerm_eventhub_consumer_group.groups : k => v.id
  }
}
