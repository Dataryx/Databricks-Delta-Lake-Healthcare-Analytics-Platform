# Governance

Entra ID groups are the only principals. The access matrix lives in
[`config/governance/access_matrix.yml`](../config/governance/access_matrix.yml) and is
applied by `make apply-governance` (generates reviewable SQL; live UC apply is
cloud/CD).

## Principles

- Least privilege / HIPAA **minimum necessary**
- No grants to individual users or `account users` on PHI-adjacent assets
- `restricted.*` is **break-glass only** (`hc_breakglass_reid`) after
  `ops.reid_request_log` justification

## Commands

```bash
make apply-governance
# artifacts/governance/grants_hc_dev.sql
# docs/lineage.md regenerated
# ops.uc_tags, ops.lineage_snapshot, ops.access_audit_daily, ops.access_review
```

## Break-glass

1. Call `request_reid(...)` with ≥20-char justification (alerts privacy officer).
2. Only then SELECT from `restricted.patient_xref`.
3. Monthly review of `ops.reid_request_log`.

## Compliance note

These are **technical safeguards that support** HIPAA expectations. Organizational
policy, BAAs, training, and audit remain required — this repo is not a certification.
