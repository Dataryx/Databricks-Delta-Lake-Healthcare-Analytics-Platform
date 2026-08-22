variable "location" {
  type        = string
  description = "Azure region (single-region UC metastore)"
  default     = "eastus2"
}

variable "resource_group_name" {
  type    = string
  default = "rg-indominus-hc-lake"
}

variable "storage_account_name" {
  type        = string
  description = "ADLS Gen2 account (must be globally unique)"
  default     = "stindominushclake"
}

variable "key_vault_name" {
  type    = string
  default = "kv-indominus-hc"
}

variable "tenant_id" {
  type        = string
  description = "Azure AD tenant for Key Vault"
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "databricks_account_id" {
  type        = string
  description = "Databricks account id for UC metastore"
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "uc_metastore_name" {
  type    = string
  default = "uc_metastore_eastus2"
}

variable "enable_databricks_resources" {
  type        = bool
  description = "Create UC metastore/catalogs (requires live Databricks credentials)"
  default     = false
}
