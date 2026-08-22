# Runbook: Schema drift response

## Symptoms
- Auto Loader / Bronze ingest fails on new columns
- Silver contract validation quarantine spike

## Steps
1. Diff landing header vs `conf/contracts/*.yml`.
2. If additive non-breaking: update contract + DQ rules; deploy via PR.
3. If breaking: stop promotion (`gate_promotion`), quarantine remaining files.
4. Backfill only after contract version bump and dual-read validation in `hc_test`.
5. Update lineage Mermaid via `make apply-governance`.
