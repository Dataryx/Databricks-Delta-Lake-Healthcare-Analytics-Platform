# Runbook: Pipeline failure triage

## Symptoms
- Job/DLT run failed; `ops.pipeline_run_log.status = failed`
- On-call email from Asset Bundle `email_notifications.on_failure`

## Steps
1. Open the failed Databricks Job / DLT run; capture error and cluster event log.
2. Confirm environment catalog (`hc_dev` / `hc_test` / `hc_prod`) — never promote fixes using prod data into lower envs.
3. Check `ops.dq_results` for fail-closed Silver gates blocking Gold.
4. Check quarantine tables for schema drift / bad rows.
5. Re-run the failed task only (Asset Bundle job task retry) after fixing root cause.
6. Log outcome with `scripts/ops_report.py --pipeline <name> --status success|failed`.

## Escalation
- Platform on-call → privacy officer if restricted schema or break-glass involved.
