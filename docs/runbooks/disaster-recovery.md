# Runbook: Disaster recovery

## Targets
- RPO: ≤ 24 hours (Delta time travel + ADLS soft delete)
- RTO: ≤ 8 hours for `hc_prod` research marts

## Steps
1. Fail over only within the same Azure region metastore (`eastus2`) unless regional DR exercise approved.
2. Restore tables via Delta time travel / deep clone from known-good version.
3. Re-apply governance grants SQL from `artifacts/governance/`.
4. Re-run freshness check (`scripts/ops_report.py`); clear SLA misses.
5. Notify research leads; invalidate stale model registry stages if features rebuilt.
