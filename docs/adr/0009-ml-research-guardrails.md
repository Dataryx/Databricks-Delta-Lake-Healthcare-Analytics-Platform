# ADR 0009: ML research guardrails (patient split, PIT features, model cards)

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Healthcare ML must avoid leakage, subgroup harm, and overclaiming clinical validity.

## Decision

1. Materialize feature tables in an `ml` schema with `feature_as_of` for point-in-time joins.
2. Split train/test by **patient_key** (never row-level).
3. Report subgroup metrics (age, sex, race/ethnicity, payer) and emit a model card per model.
4. Log to MLflow; tag Unity Catalog model names for cloud registration in Phase 10.
5. Document every model as research / decision-support — **not** a clinical device.

## Consequences

- Local demo trains sklearn models without Databricks Feature Store APIs.
- Synthetic no-show labels are explicitly simulated for pipeline proof only.
- True PDC adherence and Expert Determination remain future work.
