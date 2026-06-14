# Staging Environment — Terraform Backend (Azure Storage)

terraform {
  backend "azurerm" {
    resource_group_name  = "magenta-tfstate"
    storage_account_name = "magentatfstatestaging"
    container_name       = "tfstate"
    key                  = "soa/staging/terraform.tfstate"
    use_oidc             = true
  }
}
