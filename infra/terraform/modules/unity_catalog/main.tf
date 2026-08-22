# Unity Catalog metastore + catalogs/schemas (account-level provider)
terraform {
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.40"
    }
  }
}

variable "metastore_name" { type = string }
variable "region" { type = string }
variable "catalogs" { type = list(string) }
variable "schemas" { type = list(string) }
variable "tags" { type = map(string) }

resource "databricks_metastore" "this" {
  name          = var.metastore_name
  region        = var.region
  force_destroy = false
}

resource "databricks_catalog" "env" {
  for_each       = toset(var.catalogs)
  name           = each.value
  metastore_id   = databricks_metastore.this.id
  isolation_mode = "ISOLATED"
  comment        = "INDHC healthcare research catalog (${each.value})"
}

resource "databricks_schema" "layers" {
  for_each     = { for p in setproduct(var.catalogs, var.schemas) : "${p[0]}.${p[1]}" => p }
  catalog_name = each.value[0]
  name         = each.value[1]
  comment      = "Managed schema ${each.value[1]} in ${each.value[0]}"
  depends_on   = [databricks_catalog.env]
}

output "metastore_id" {
  value = databricks_metastore.this.id
}
