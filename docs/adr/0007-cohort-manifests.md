# ADR 0007: Declarative YAML cohorts + checksum manifests

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Research reproducibility requires pinning inputs and proving re-derivation.

## Decision

1. Define cohorts in YAML (inclusion/exclusion/index/follow-up).
2. Materialize to Gold with a definition hash.
3. Emit `RESEARCH_MANIFEST.json` with Delta versions + output checksum.
4. `reproduce.py` rebuilds and asserts checksum equality on stable key columns.

## Consequences

- Reviewable cohort logic in PRs.
- Checksums ignore volatile timestamps (`built_at`) by hashing
  `patient_sk|cohort_name|definition_hash` only.
