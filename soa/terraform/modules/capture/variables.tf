# Capture Module Variables

variable "environment" {
  description = "Deployment environment"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Must be dev, staging, or production."
  }
}

variable "resource_prefix" {
  description = "Prefix for resource naming"
  type        = string
  default     = "magenta"
}

variable "resource_group_name" {
  description = "Azure resource group name"
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

variable "capture_topics" {
  description = "Event Hubs topics with Capture enabled"
  type        = list(string)
  default     = ["raw-logs", "raw-alerts", "enriched-alerts", "enriched-events", "audit", "dead-letter"]
}

variable "topic_partitions" {
  description = "Partition count per topic"
  type        = map(number)
  default = {
    "raw-logs"        = 16
    "raw-alerts"      = 8
    "enriched-alerts" = 8
    "enriched-events" = 8
    "audit"           = 4
    "dead-letter"     = 1
  }
}

variable "topic_retention_days" {
  description = "Message retention in days per topic"
  type        = map(number)
  default = {
    "raw-logs"        = 7
    "raw-alerts"      = 7
    "enriched-alerts" = 1
    "enriched-events" = 1
    "audit"           = 7
    "dead-letter"     = 2
  }
}

variable "eventhub_sku" {
  description = "Event Hubs SKU (Basic, Standard, Premium)"
  type        = string
  default     = "Standard"
}

variable "eventhub_capacity" {
  description = "Event Hubs throughput units (Standard) or processing units (Premium)"
  type        = number
  default     = 2
}

variable "max_throughput_units" {
  description = "Maximum auto-inflate throughput units (Standard only)"
  type        = number
  default     = 8
}

variable "consumer_groups" {
  description = "Consumer groups to create per topic"
  type        = list(string)
  default     = ["$Default", "normalizer", "log-normalizer", "vectorizer-logs", "orchestrator", "registry", "dlq-debug"]
}
