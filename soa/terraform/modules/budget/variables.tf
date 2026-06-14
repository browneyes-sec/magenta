# Budget Module Variables

variable "environment" {
  description = "Deployment environment"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "resource_group_name" {
  description = "Resource group for the budget action group"
  type        = string
  default     = "magenta-monitoring"
}

variable "monthly_budget_total" {
  description = "Total monthly budget amount in USD"
  type        = number
}

variable "provider_budgets" {
  description = "Per-provider monthly budgets in USD (tag-based)"
  type        = map(number)
  default = {
    azure    = 1500
    aws      = 500
  }
}

variable "alert_thresholds" {
  description = "Alert thresholds in percentage (0-100)"
  type        = list(number)
  default     = [50, 80, 95]
  validation {
    condition     = alltrue([for t in var.alert_thresholds : t >= 1 && t <= 100])
    error_message = "Alert thresholds must be between 1 and 100."
  }
}

variable "enable_block_threshold" {
  description = "Enable forecasted 100% threshold to trigger block action"
  type        = bool
  default     = false
}

variable "notification_email" {
  description = "Email address for budget alerts"
  type        = string
  default     = "finops@magenta.local"
}

variable "webhook_url" {
  description = "Webhook URL for budget alerts (e.g., Slack)"
  type        = string
  default     = ""
}

variable "alert_roles" {
  description = "RBAC role IDs to notify"
  type        = list(string)
  default     = []
}

variable "filter_tags" {
  description = "Tags to filter budget scope"
  type        = map(list(string))
  default = {
    environment = ["dev", "staging", "production"]
    project     = ["magenta"]
  }
}

variable "tags" {
  description = "Tags to apply to budget resources"
  type        = map(string)
  default     = {}
}
