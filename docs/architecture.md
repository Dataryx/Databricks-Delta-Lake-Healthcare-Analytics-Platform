# Architecture

This lakehouse is built for Indominus Health Research Consortium (INDHC) on Azure
Databricks and Delta Lake. The same Python package runs locally with PySpark and
delta-spark, so engineers can develop and demo without a workspace.

## Pipeline

```mermaid
flowchart LR
  Landing[Landing CSV / Auto Loader] --> Bronze[Bronze raw + change feed]
  Bronze --> Silver[Silver conformed + Safe Harbor]
  Silver --> Restricted[restricted.patient_xref]
  Silver --> Gold[Gold dimensions, facts, marts]
  Gold --> Cohorts[Research cohorts]
  Gold --> Features[ml feature tables]
  Features --> Models[MLflow research models]
  Gold --> Dashboards[SQL warehouse dashboards]
  DQ[Fail-closed DQ] -.-> Silver
  DQ -.-> Gold
  Gov[Grants + lineage] -.-> Silver
  Gov -.-> Gold
```

Bronze keeps the raw feed with technical columns and change data feed. Silver
cleanses, validates, and de-identifies. Gold is the Kimball layer researchers
actually query. Restricted crosswalk tables stay tightly gated.

## Azure shape

```mermaid
flowchart TB
  subgraph Azure["eastus2"]
    ADLS[ADLS Gen2]
    ADB[Databricks Premium]
    AKV[Key Vault]
    UC[Unity Catalog metastore]
  end
  ADLS --> ADB
  AKV --> ADB
  UC --> ADB
  TF[Terraform] -.-> ADLS
  TF -.-> UC
  Bundles[Asset Bundles] -.-> ADB
```

Local mode swaps ADLS paths for a folder under `.local_delta/` and skips live
Unity Catalog grant APIs. Grant SQL is still generated so it can be reviewed and
applied in the workspace.

## Environments

| Environment | Catalog | Data |
|-------------|---------|------|
| local / dev | `hc_dev` | Synthetic only |
| test | `hc_test` | Synthetic or approved fixtures |
| prod | `hc_prod` | Controlled research data (org-managed) |

Prod data does not flow back into lower environments.
