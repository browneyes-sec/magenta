# AWS CloudTrail Module Variables

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "resource_prefix" {
  description = "Prefix for resource naming"
  type        = string
  default     = "magenta"
}

variable "common_tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}

variable "kms_key_id" {
  description = "KMS key ID for CloudTrail encryption (optional)"
  type        = string
  default     = ""
}

variable "enable_partner_eventhub" {
  description = "Enable EventBridge rule to push to partner Event Hub"
  type        = bool
  default     = false
}

variable "partner_eventhub_arn" {
  description = "ARN of partner Event Hub (e.g., Azure Event Hubs partner integration)"
  type        = string
  default     = ""
}

variable "collector_role_arn" {
  description = "ARN of the Magenta collector IAM role (cross-account)"
  type        = string
  default     = ""
}
