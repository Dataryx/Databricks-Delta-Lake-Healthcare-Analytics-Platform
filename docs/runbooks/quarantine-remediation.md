# Runbook: Quarantine remediation

## Steps
1. Query quarantine Delta for `error_code` / `rule_id`.
2. Classify: source defect vs transform bug vs contract too strict.
3. Fix source or code; do **not** silently drop bad rows in Silver.
4. Re-ingest corrected files; confirm DQ gate green before Gold.
5. Document in ops ticket with sample synthetic keys only (no PHI).
