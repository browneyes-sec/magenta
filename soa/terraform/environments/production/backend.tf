# Production Environment — Terraform Backend (Azure Storage)

terraform {
  backend "azurerm" {
    resource_group_name  = "magenta-tfstate"
    storage_account_name = "magentatfstateprod"
    container_name       = "tfstate"
    key                  = "soa/production/terraform.tfstate"
    use_oidc             = true
  }
}
