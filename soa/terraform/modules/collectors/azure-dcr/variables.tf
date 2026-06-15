# Azure DCR Module Variables

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "resource_prefix" {
  description = "Prefix for resource naming"
  type        = string
  default     = "magenta"
}

variable "resource_group_name" {
  description = "Azure resource group"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus2"
}

variable "common_tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}

variable "eventhub_id" {
  description = "Event Hubs ID for DCR destination"
  type        = string
}

variable "eventhub_namespace_id" {
  description = "Event Hubs namespace ID for diagnostic settings"
  type        = string
}

variable "eventhub_topic_name" {
  description = "Event Hubs topic name (raw-logs)"
  type        = string
  default     = "raw-logs"
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace resource ID"
  type        = string
  default     = ""
}

variable "key_vault_ids" {
  description = "Key Vault resource IDs for diagnostic settings"
  type        = list(string)
  default     = []
}

variable "aks_cluster_ids" {
  description = "AKS cluster resource IDs for diagnostic settings"
  type        = list(string)
  default     = []
}

variable "syslog_facilities" {
  description = "Syslog facility names for DCR"
  type        = list(string)
  default     = ["auth", "authpriv", "cron", "daemon", "kern", "local0", "local1", "local2", "local3", "local4", "local5", "local6", "local7", "lpr", "mail", "mark", "news", "syslog", "user", "uucp"]
}

variable "syslog_log_levels" {
  description = "Syslog log levels for DCR"
  type        = list(string)
  default     = ["Debug", "Info", "Notice", "Warning", "Error", "Critical", "Alert", "Emergency"]
}

variable "performance_counters" {
  description = "Performance counter specifiers"
  type        = list(string)
  default     = ["\\Processor Information(_Total)\\% Processor Time", "\\Memory\\Available Bytes", "\\LogicalDisk(_Total)\\% Free Space"]
}
