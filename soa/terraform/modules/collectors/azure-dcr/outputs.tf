# Azure DCR Module Outputs

output "dcr_id" {
  description = "Data Collection Rule ID"
  value       = azurerm_monitor_data_collection_rule.dcr.id
}

output "dcr_name" {
  description = "Data Collection Rule name"
  value       = azurerm_monitor_data_collection_rule.dcr.name
}

output "diagnostic_setting_ids" {
  description = "Diagnostic setting resource IDs"
  value = {
    log_analytics = try(azurerm_monitor_diagnostic_setting.la_to_eventhub.id, null)
    key_vaults    = { for k, v in azurerm_monitor_diagnostic_setting.kv_to_eventhub : k => v.id }
    aks_clusters  = { for k, v in azurerm_monitor_diagnostic_setting.aks_to_eventhub : k => v.id }
  }
}
