# Architecture

Indominus Health Research Consortium (INDHC) lakehouse on Azure Databricks + Delta Lake.
Local mode runs the same Python package with PySpark + `delta-spark`.

## End-to-end flow

```mermaid
flowchart LR
  Landing[Landing CSV / Auto Loader] --> Bronze[Bronze raw + CDF]
  Bronze --> Silver[Silver conformed + Safe Harbor]
  Silver --> Restricted[restricted.patient_xref]
  Silver --> Gold[Gold dims facts marts]
  Gold --> Cohorts[Research cohorts]
  Gold --> Features[ml.ft_* features]
  Features --> ML[MLflow research models]
  Gold --> Serving[SQL dashboards / warehouse]
  DQ[DQ fail-closed] -.-> Silver
  DQ -.-> Gold
  Gov[UC grants + lineage] -.-> Silver
  Gov -.-> Gold
```

## Azure landing zone

```mermaid
flowchart TB
  subgraph Azure["eastus2"]
    ADLS[ADLS Gen2 HNS]
    ADB[Databricks Premium]
    AKV[Key Vault]
    UC[UC metastore]
  end
  ADLS --> ADB
  AKV --> ADB
  UC --> ADB
  TF[Terraform] -.-> ADLS
  TF -.-> UC
  DAB[Asset Bundles] -.-> ADB
```

## Environment isolation

| Env | Catalog | Data |
|-----|---------|------|
| local/dev | `hc_dev` | Synthetic only |
| test | `hc_test` | Synthetic / approved fixtures |
| prod | `hc_prod` | Controlled research data (org-managed) |

Production data never flows backward into dev.
