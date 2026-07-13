# Ingest Gateway Module Outputs

output "gateway_id" {
  description = "Application Gateway resource ID"
  value       = azurerm_application_gateway.ingest_gateway.id
}

output "gateway_fqdn" {
  description = "Public FQDN of ingest gateway"
  value       = "ingest.${var.dns_zone_name}"
}

output "public_ip" {
  description = "Public IP address"
  value       = azurerm_public_ip.ingress.ip_address
}

output "waf_policy_id" {
  description = "WAF policy resource ID (if attached)"
  value       = try(azurerm_application_gateway.ingest_gateway.waf_policy_id, null)
}
