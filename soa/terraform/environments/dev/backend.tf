# Dev Environment — Terraform Backend (Azure Storage)

terraform {
  backend "azurerm" {
    resource_group_name  = "magenta-tfstate"
    storage_account_name = "magentatfstatedev"
    container_name       = "tfstate"
    key                  = "soa/dev/terraform.tfstate"
    use_oidc             = true
  }
}
