# Budget Module Outputs

output "action_group_id" {
  description = "ID of the budget alert action group"
  value       = azurerm_monitor_action_group.budget.id
}

output "overall_budget_id" {
  description = "ID of the overall subscription budget"
  value       = azurerm_consumption_budget_subscription.overall.id
}

output "provider_budget_ids" {
  description = "IDs of per-provider budgets"
  value = {
    for k, v in azurerm_consumption_budget_subscription.provider : k => v.id
  }
}

output "monthly_limit" {
  description = "Configured monthly budget limit"
  value       = var.monthly_budget_total
}
