# ADR 0002: Python Synthea-compatible simulator vs. full Synthea JAR

- **Status:** Accepted
- **Date:** 2026-08-21

## Context

Mission specifies Synthea as the synthetic clinical source. Running the Synthea JAR
in every developer/CI environment adds Java/module friction and non-deterministic
exports unless carefully pinned.

## Decision

Ship a deterministic Python generator (`synthea_sim`) that emits Synthea-like entity
shapes (patients, encounters, conditions, labs, meds, procedures, immunizations,
claims, consents) plus a PRO survey simulator. Document optional future wiring to
the official Synthea CLI for larger corpora.

## Consequences

- `make generate-synthetic` works offline with seed=42.
- Landing schemas stay stable for Bronze Auto Loader contracts.
- Stewards can later swap the generator for true Synthea CSV drops without changing
  Bronze table names.
