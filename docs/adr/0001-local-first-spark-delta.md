# ADR 0001: Local-first runnable Lakehouse with cloud parity

- **Status:** Accepted
- **Date:** 2026-08-21
- **Deciders:** Platform architecture (Indominus Health Research Consortium)

## Context

The platform must be demonstrable without an Azure subscription while remaining the same
codebase that deploys to Azure Databricks + Unity Catalog. Reviewers need `make demo` /
`make test` on a laptop.

## Decision

1. Use **PySpark + delta-spark** as the local execution engine.
2. Abstract session creation in `hc_lakehouse.utils.spark_session.get_spark`.
3. When `HC_RUNTIME_MODE=databricks`, attempt Databricks Connect; on failure **log and fall
   back to local** rather than crash.
4. Keep Unity Catalog names (`catalog.schema.table`) as logical identifiers; local mode maps
   them to filesystem Delta paths under `HC_LOCAL_DELTA_ROOT`.

## Consequences

- Developers can iterate offline with synthetic data.
- Cloud-only features (Auto Loader `cloudFiles`, UC masks, system tables) must degrade with
  explicit log messages and local substitutes.
- CI runs Spark integration tests on Ubuntu with Temurin JDK 17.
