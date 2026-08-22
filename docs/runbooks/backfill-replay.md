# Runbook: Backfill / replay

## When
- Late-arriving landing files
- Incorrect partition overwrite
- Need to rebuild Silver/Gold for a date range

## Steps
1. Identify watermark / date range; never full-overwrite prod without change ticket.
2. Re-stage synthetic or approved landing files under `landing/`.
3. Local: `make ingest-bronze build-silver run-dq build-gold`.
4. Cloud: trigger DLT refresh then `hc_gold_cohort_ml` job.
5. Verify row counts and `RESEARCH_MANIFEST.json` checksums for affected cohorts.
6. Record run in `ops.pipeline_run_log`.

## RPO / RTO (targets)
- RPO: 24h (daily Gold SLA)
- RTO: 4h for critical research marts after triage
