# Orchestration and CI/CD

## Local vs cloud

| Concern | Local (`make demo`) | Cloud (Databricks) |
|---------|---------------------|--------------------|
| Bronze→Silver | Batch scripts | DLT `pipelines/dlt/bronze_silver_dlt.py` |
| Gold→ML | Make targets | Job `hc_gold_cohort_ml` in Asset Bundle |
| Infra | N/A | Terraform `infra/terraform` |
| Deploy | N/A | `databricks bundle deploy -t dev\|test\|prod` |

## Asset Bundle

- Root: [`databricks.yml`](../databricks.yml)
- Resources: [`resources/jobs.yml`](../resources/jobs.yml), [`resources/pipelines.yml`](../resources/pipelines.yml)
- Cluster policy JSON: [`conf/cluster_policies/hc_job_policy.json`](../conf/cluster_policies/hc_job_policy.json)
- SLA config: [`conf/ops/sla.yml`](../conf/ops/sla.yml)

Jobs use retries with exponential backoff intervals, timeouts, failure email notifications,
and spot-with-fallback where allowed.

## Ops tables

- `ops.pipeline_run_log` — duration, rows, cost proxy, status
- `ops.table_freshness` — SLA miss detection
- Monthly cost SQL: `scripts/ops_report.py` → `artifacts/ops/monthly_cost_report.sql`

## CI/CD

- PR CI: ruff, mypy, pytest, PHI scan, grants dry-run, terraform validate, bundle structure check
- CD: manual `workflow_dispatch` with GitHub Environment approval on **prod**

## Runbooks

See [`docs/runbooks/`](runbooks/).
