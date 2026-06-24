# Azure DCR → Event Hubs Module
# Configures Diagnostic Settings to stream Azure Monitor / Log Analytics
# logs directly to Event Hubs for consumption by the Log Normalizer.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

# ── Data Collection Rule ─────────────────────────────────────────────────

resource "azurerm_monitor_data_collection_rule" "dcr" {
  name                = "${var.resource_prefix}-${var.environment}-dcr"
  resource_group_name = var.resource_group_name
  location            = var.location
  kind                = "Linux"

  data_sources {
    syslog {
      facility_names = var.syslog_facilities
      log_levels     = var.syslog_log_levels
      name           = "syslog-logs"
      streams        = ["Microsoft-Syslog"]
    }

    performance_counter {
      streams                  = ["Microsoft-InsightsMetrics"]
      sampling_frequency_in_seconds = 60
      counter_specifiers       = var.performance_counters
      name                     = "perf-counters"
    }
  }

  destinations {
    event_hub {
      event_hub_id = var.eventhub_id
      name         = "eventhub-destination"
    }
  }

  data_flow {
    streams      = ["Microsoft-Syslog", "Microsoft-InsightsMetrics"]
    destinations = ["eventhub-destination"]
  }

  tags = var.common_tags
}

# ── Diagnostic Settings for Log Analytics Workspace ─────────────────────

resource "azurerm_monitor_diagnostic_setting" "la_to_eventhub" {
  name               = "${var.resource_prefix}-${var.environment}-la-to-eventhub"
  target_resource_id = var.log_analytics_workspace_id
  eventhub_name      = var.eventhub_topic_name
  eventhub_namespace_id = var.eventhub_namespace_id
  enabled_log {
    category = "AuditLogs"
  }
  enabled_log {
    category = "SignInLogs"
  }
  enabled_log {
    category = "SecurityEvent"
  }
  enabled_log {
    category = "AzureActivity"
  }
  metric {
    category = "AllMetrics"
  }
}

# ── Diagnostic Settings for Key Vault ───────────────────────────────────

resource "azurerm_monitor_diagnostic_setting" "kv_to_eventhub" {
  for_each             = toset(var.key_vault_ids)
  name                 = "${var.resource_prefix}-${var.environment}-kv-to-eventhub"
  target_resource_id   = each.value
  eventhub_name        = var.eventhub_topic_name
  eventhub_namespace_id = var.eventhub_namespace_id

  enabled_log {
    category = "AuditEvent"
  }
}

# ── Diagnostic Settings for AKS ─────────────────────────────────────────

resource "azurerm_monitor_diagnostic_setting" "aks_to_eventhub" {
  for_each             = toset(var.aks_cluster_ids)
  name                 = "${var.resource_prefix}-${var.environment}-aks-to-eventhub"
  target_resource_id   = each.value
  eventhub_name        = var.eventhub_topic_name
  eventhub_namespace_id = var.eventhub_namespace_id

  enabled_log {
    category = "kube-audit"
  }
  enabled_log {
    category = "kube-audit-admin"
  }
  enabled_log {
    category = "guard"
  }
}
