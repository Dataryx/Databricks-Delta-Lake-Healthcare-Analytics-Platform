# ADR 0010: DLT for Bronze/Silver + Workflows DAG for Gold/ML

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Streaming expectations fit Bronze→Silver; Gold/cohort/ML are batch DAGs with
explicit dependencies and cost controls.

## Decision

1. Use **Delta Live Tables** for Bronze→Silver (Auto Loader + expectations).
2. Use **Databricks Workflows** (Asset Bundles) for Gold → cohort → features → ML → governance.
3. Manage Azure/UC objects with **Terraform**; deploy jobs/pipelines with **Asset Bundles**.
4. Enforce job compute via cluster policy JSON; prefer spot-with-fallback for non-critical work.
5. Local PySpark scripts remain the demo path; cloud features degrade gracefully when offline.

## Consequences

- Two runtimes (local scripts vs DLT) must stay semantically aligned via shared `hc_lakehouse` package.
- Prod CD requires GitHub Environment approval and workspace secrets.
