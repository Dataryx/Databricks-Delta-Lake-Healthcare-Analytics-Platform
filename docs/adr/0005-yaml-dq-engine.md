# ADR 0005: YAML DQ rules + validate() instead of DLT-only expectations

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Mission requires DLT expectations and a reusable `validate(df, ruleset)` for
non-DLT paths. Local demo cannot run DLT.

## Decision

1. Author rules once in `conf/quality/*.yml`.
2. Implement `validate()` with the same semantics (severity, threshold, categories).
3. Persist every execution to `ops.dq_results`.
4. `gate_promotion` fails closed on error severity; warn/info never block.
5. DLT notebooks (Phase 10) will generate expectations from the same YAML.

## Consequences

- CI and `make demo` exercise real DQ without a Databricks workspace.
- Stewards review rule PRs; thresholds are reviewable.
