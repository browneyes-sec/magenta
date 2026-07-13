# Azure Budget Module
# Creates monthly budgets with email and webhook alerts at configurable thresholds.
# Supports multi-cloud cost allocation tracking via tags.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }
}

# ── Budget Action Group (Notifications) ──────────────────────────────────

resource "azurerm_monitor_action_group" "budget" {
  name                = "magenta-budget-${var.environment}"
  resource_group_name = var.resource_group_name
  short_name          = "mag-budget"

  email_receiver {
    name                    = "finops-team"
    email_address           = var.notification_email
    use_common_alert_schema = true
  }

  dynamic "webhook_receiver" {
    for_each = var.webhook_url != "" ? [1] : []
    content {
      name                    = "slack-webhook"
      service_uri             = var.webhook_url
      use_common_alert_schema = true
    }
  }

  tags = var.tags
}

# ── Monthly Budgets per Scope ────────────────────────────────────────────

resource "azurerm_consumption_budget_subscription" "overall" {
  name            = "magenta-${var.environment}-overall"
  subscription_id = data.azurerm_subscription.current.id
  amount          = var.monthly_budget_total

  time_grain = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01", timeadd(timestamp(), "0h"))
  }

  notification {
    enabled   = true
    threshold = var.alert_thresholds[0]
    operator  = "EqualToOrGreaterThan"
    contact_emails = [var.notification_email]
    contact_groups = []

    dynamic "contact_roles" {
      for_each = var.alert_roles
      content {
        role_definition_id = data.azurerm_role_definition.contributor.id
      }
    }
  }

  notification {
    enabled   = true
    threshold = var.alert_thresholds[1]
    operator  = "EqualToOrGreaterThan"
    contact_emails = [var.notification_email]
  }

  notification {
    enabled   = true
    threshold = var.alert_thresholds[2]
    operator  = "EqualToOrGreaterThan"
    contact_emails = [var.notification_email]
  }

  dynamic "notification" {
    for_each = var.enable_block_threshold ? [1] : []
    content {
      enabled       = true
      threshold     = 100
      operator      = "EqualToOrGreaterThan"
      threshold_type = "Forecasted"
      contact_emails = [var.notification_email]
    }
  }

  filter {
    dynamic "dimension" {
      for_each = var.filter_tags
      content {
        name        = dimension.key
        operator    = "In"
        values      = dimension.value
      }
    }
  }

  tags = var.tags
}

# ── Per-Provider Sub-Budgets ─────────────────────────────────────────────

resource "azurerm_consumption_budget_subscription" "provider" {
  for_each = var.provider_budgets

  name            = "magenta-${var.environment}-${each.key}"
  subscription_id = data.azurerm_subscription.current.id
  amount          = each.value

  time_grain = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01", timeadd(timestamp(), "0h"))
  }

  notification {
    enabled   = true
    threshold = var.alert_thresholds[0]
    operator  = "EqualToOrGreaterThan"
    contact_emails = [var.notification_email]
  }

  notification {
    enabled   = true
    threshold = var.alert_thresholds[1]
    operator  = "EqualToOrGreaterThan"
    contact_emails = [var.notification_email]
  }

  filter {
    tag {
      name     = "provider"
      operator = "In"
      values   = [each.key]
    }
  }

  tags = var.tags
}

# ── Data Sources ─────────────────────────────────────────────────────────

data "azurerm_subscription" "current" {}

data "azurerm_role_definition" "contributor" {
  name = "Contributor"
}
