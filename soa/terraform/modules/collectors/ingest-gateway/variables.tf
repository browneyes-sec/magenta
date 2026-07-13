# Ingest Gateway Module Variables

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

variable "gateway_subnet_id" {
  description = "Subnet ID for Application Gateway (dedicated /24+)"
  type        = string
}

variable "gateway_capacity" {
  description = "WAF v2 capacity units"
  type        = number
  default     = 2
}

variable "ingest_api_fqdns" {
  description = "FQDNs of ingest API backend instances"
  type        = list(string)
}

variable "dns_zone_name" {
  description = "Public DNS zone name (e.g., magenta.example.com)"
  type        = string
  default     = ""
}

variable "dns_zone_resource_group" {
  description = "Resource group containing DNS zone"
  type        = string
  default     = ""
}

variable "ssl_certificate_data" {
  description = "Base64-encoded PFX certificate for ingress"
  type        = string
}

variable "ssl_certificate_password" {
  description = "PFX password"
  type        = string
  sensitive   = true
}

variable "client_ca_certificate_data" {
  description = "Base64-encoded CA certificate for mTLS client verification"
  type        = string
}

variable "client_ca_issuer_dn" {
  description = "Expected issuer DN for client certificates"
  type        = string
  default     = ""
}

variable "key_vault_id" {
  description = "Key Vault ID for secret storage"
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID for gateway logs"
  type        = string
  default     = ""
}
