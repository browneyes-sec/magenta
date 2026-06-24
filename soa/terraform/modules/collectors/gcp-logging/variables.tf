# GCP Logging Module Variables

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "resource_prefix" {
  description = "Prefix for resource naming"
  type        = string
  default     = "magenta"
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "common_tags" {
  description = "Labels applied to all resources"
  type        = map(string)
  default     = {}
}

variable "enable_eventhub_forwarder" {
  description = "Deploy Cloud Run job to forward logs to Event Hubs"
  type        = bool
  default     = false
}

variable "forwarder_image" {
  description = "Container image for Event Hubs forwarder"
  type        = string
  default     = "magenta/eventhub-forwarder:latest"
}

variable "eventhub_namespace" {
  description = "Azure Event Hubs namespace"
  type        = string
  default     = ""
}

variable "eventhub_topic" {
  description = "Event Hubs topic name (raw-logs)"
  type        = string
  default     = "raw-logs"
}

variable "forwarder_service_account" {
  description = "Service account for forwarder job"
  type        = string
  default     = ""
}

variable "collector_service_account" {
  description = "Magenta collector service account email"
  type        = string
  default     = ""
}
