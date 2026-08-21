# Architecture

Phase 0 establishes the executable skeleton. Full medallion, Unity Catalog, and Azure
landing-zone detail is expanded in later phases. See `ASSUMPTIONS.md` for resolved defaults.

```mermaid
flowchart TB
  subgraph Azure["Azure landing zone (eastus2)"]
    ADLS[ADLS Gen2 containers]
    ADB[Databricks Premium VNet-injected]
    AKV[Key Vault / CMK]
    UC[Unity Catalog metastore]
  end
  subgraph Medallion
    B[Bronze]
    S[Silver]
    G[Gold]
  end
  ADLS --> ADB
  ADB --> B --> S --> G
  AKV --> ADB
  UC --> ADB
```

Local mode replaces ADLS paths with `.local_delta/` and skips Private Link / UC grant APIs.
