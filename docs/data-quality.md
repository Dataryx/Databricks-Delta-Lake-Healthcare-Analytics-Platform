# Data quality framework

Fail-closed validation for Silver (and later Gold) tables.

## Rules as code

YAML under `config/quality/`:

| File | Table |
|------|-------|
| `silver_patient.yml` | `silver.patient` |
| `silver_encounter.yml` | `silver.encounter` |
| `silver_lab_result.yml` | `silver.lab_result` |

Categories: completeness, validity, range, uniqueness, consistency, timeliness.
Severities: `info` / `warn` / `error` (only **error** blocks promotion).

## Engine

```python
from hc_lakehouse.quality import load_ruleset, validate, gate_promotion

report = validate(df, load_ruleset("silver_patient"))
gate_promotion(report)  # raises PromotionBlockedError on error failures
```

Results append to `ops.dq_results`. Scorecard: latest status per table/rule.

## CLI

```bash
make build-silver   # also writes DQ results
make run-dq         # enforce Silver→Gold gate
```

Alerts: structured log always; optional `HC_ALERT_TEAMS_WEBHOOK` / `HC_ALERT_EMAIL_WEBHOOK`.
