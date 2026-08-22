# Azure + Unity Catalog landing zone for INDHC healthcare research Lakehouse
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.40"
    }
  }
}

provider "azurerm" {
  features {}
}

# Account-level Databricks provider for metastore/assignment (cloud)
provider "databricks" {
  alias      = "account"
  host       = "https://accounts.azuredatabricks.net"
  account_id = var.databricks_account_id
}

locals {
  tags = {
    org         = "INDHC"
    project     = "hc-lakehouse"
    cost_center = "INDHC-Research"
    managed_by  = "terraform"
  }
  catalogs = ["hc_dev", "hc_test", "hc_prod"]
  schemas  = ["bronze", "silver", "gold", "ml", "ops", "restricted", "sandbox"]
}

resource "azurerm_resource_group" "hc" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.tags
}

resource "azurerm_storage_account" "lake" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.hc.name
  location                 = azurerm_resource_group.hc.location
  account_tier             = "Standard"
  account_replication_type = "ZRS"
  is_hns_enabled           = true
  min_tls_version          = "TLS1_2"
  tags                     = local.tags
}

resource "azurerm_storage_container" "layers" {
  for_each              = toset(["landing", "bronze", "silver", "gold", "quarantine", "checkpoints"])
  name                  = each.value
  storage_account_name  = azurerm_storage_account.lake.name
  container_access_type = "private"
}

resource "azurerm_key_vault" "hc" {
  name                       = var.key_vault_name
  location                   = azurerm_resource_group.hc.location
  resource_group_name        = azurerm_resource_group.hc.name
  tenant_id                  = var.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 90
  purge_protection_enabled   = true
  tags                       = local.tags
}

# Workspace / UC objects are environment-gated so `terraform validate` works offline.
# Apply requires authenticated Azure + Databricks providers.
module "unity_catalog" {
  source = "./modules/unity_catalog"
  count  = var.enable_databricks_resources ? 1 : 0

  providers = {
    databricks = databricks.account
  }

  metastore_name = var.uc_metastore_name
  region         = var.location
  catalogs       = local.catalogs
  schemas        = local.schemas
  tags           = local.tags
}

output "resource_group" {
  value = azurerm_resource_group.hc.name
}

output "storage_account" {
  value = azurerm_storage_account.lake.name
}

output "containers" {
  value = [for c in azurerm_storage_container.layers : c.name]
}
