# Ingest Gateway Module
# Deploys HTTPS ingress + Azure Front Door / Application Gateway
# for the Magenta ingest API with mTLS termination and WAF.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

# ── Public IP + DNS ──────────────────────────────────────────────────────

resource "azurerm_public_ip" "ingress" {
  name                = "${var.resource_prefix}-${var.environment}-ingest-pip"
  resource_group_name = var.resource_group_name
  location            = var.location
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.common_tags
}

resource "azurerm_dns_a_record" "ingest" {
  count               = var.dns_zone_name != "" ? 1 : 0
  name                = "ingest"
  zone_name           = var.dns_zone_name
  resource_group_name = var.dns_zone_resource_group
  ttl                 = 300
  records             = [azurerm_public_ip.ingress.ip_address]
}

# ── Application Gateway (WAF + mTLS termination) ─────────────────────────

resource "azurerm_application_gateway" "ingest_gateway" {
  name                = "${var.resource_prefix}-${var.environment}-ingest-gw"
  resource_group_name = var.resource_group_name
  location            = var.location

  sku {
    name     = "WAF_v2"
    tier     = "WAF_v2"
    capacity = var.gateway_capacity
  }

  gateway_ip_configuration {
    name      = "gw-ip-config"
    subnet_id = var.gateway_subnet_id
  }

  frontend_port {
    name = "https-port"
    port = 443
    protocol = "Https"
  }

  frontend_ip_configuration {
    name                 = "public-ip"
    public_ip_address_id = azurerm_public_ip.ingress.id
  }

  backend_address_pool {
    name = "ingest-api-pool"
    fqdns = var.ingest_api_fqdns
  }

  backend_http_settings {
    name                  = "ingest-api-https"
    port                  = 443
    protocol              = "Https"
    cookie_based_affinity = "Disabled"
    request_timeout       = 60
    probe_name            = "ingest-health-probe"
    trusted_root_certificate_names = [azurerm_application_gateway_trusted_root_certificate.ca.name]
  }

  http_listener {
    name                           = "https-listener"
    frontend_ip_configuration_name = "public-ip"
    frontend_port_name             = "https-port"
    protocol                       = "Https"
    ssl_certificate_name           = azurerm_application_gateway_ssl_certificate.ingest.name
    require_server_name_indication = true
    host_name                      = var.join(".", ["ingest", var.dns_zone_name])
  }

  request_routing_rule {
    name                       = "ingest-rule"
    rule_type                  = "Basic"
    http_listener_name         = "https-listener"
    backend_address_pool_name  = "ingest-api-pool"
    backend_http_settings_name = "ingest-api-https"
    priority                   = 100
  }

  # Health probe
  probe {
    name                = "ingest-health-probe"
    protocol            = "Https"
    host                = var.ingest_api_fqdns[0]
    path                = "/ingest/v1/health"
    interval            = 30
    timeout             = 10
    unhealthy_threshold = 3
    match {
      status_codes = ["200"]
    }
  }

  # WAF Configuration
  waf_configuration {
    enabled             = true
    firewall_mode       = "Prevention"
    rule_set_type       = "OWASP"
    rule_set_version    = "3.2"
    disabled_rule_groups = []
  }

  # SSL Certificate (App Gateway managed)
  ssl_certificate {
    name = "ingest-ssl-cert"
    data = var.ssl_certificate_data
    password = var.ssl_certificate_password
  }

  # Trusted CA for mTLS (client cert verification)
  trusted_root_certificate {
    name = "client-ca"
    data = var.client_ca_certificate_data
  }

  # Client Certificate Authentication (mTLS)
  ssl_profile {
    name          = "ingest-mtls"
    ssl_policy_type = "Custom"
    min_protocol_version = "TLSv1_2"
    cipher_suites = [
      "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
      "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
      "TLS_DHE_RSA_WITH_AES_256_GCM_SHA384",
      "TLS_DHE_RSA_WITH_AES_128_GCM_SHA256"
    ]
    client_auth_configuration {
      verify_client_cert = "Required"
      verify_client_cert_issuer_dn = var.client_ca_issuer_dn
    }
  }

  tags = var.common_tags
}

# ── Key Vault References for Secrets ────────────────────────────────────

resource "azurerm_key_vault_secret" "ssl_cert_password" {
  name         = "ingest-gw-ssl-cert-password"
  key_vault_id = var.key_vault_id
  value        = var.ssl_certificate_password
  tags         = var.common_tags
}

resource "azurerm_key_vault_secret" "client_ca" {
  name         = "ingest-gw-client-ca"
  key_vault_id = var.key_vault_id
  value        = var.client_ca_certificate_data
  tags         = var.common_tags
}

# ── Diagnostic Settings → Log Analytics ──────────────────────────────────

resource "azurerm_monitor_diagnostic_setting" "gateway_logs" {
  name                       = "${var.resource_prefix}-${var.environment}-gateway-logs"
  target_resource_id         = azurerm_application_gateway.ingest_gateway.id
  log_analytics_workspace_id = var.log_analytics_workspace_id
  log {
    category = "ApplicationGatewayAccessLog"
    enabled  = true
  }
  log {
    category = "ApplicationGatewayPerformanceLog"
    enabled  = true
  }
  log {
    category = "ApplicationGatewayFirewallLog"
    enabled  = true
  }
  metric {
    category = "AllMetrics"
    enabled  = true
  }
}
