# Gold layer

Kimball-style dimensional models and research marts built from validated Silver.

## Promotion gate

`build_gold` calls `validate_all_silver(..., enforce_gate=True)` first. Any
**error**-severity DQ failure blocks Gold (fail closed).

## Tables delivered (Phase 6)

| Table | Grain |
|-------|-------|
| `gold.dim_date` | calendar day |
| `gold.dim_patient` | current patient_sk |
| `gold.dim_care_setting` | care setting |
| `gold.dim_lab_test` | LOINC |
| `gold.fact_encounter` | encounter |
| `gold.fact_lab_result` | resulted lab |
| `gold.fact_readmission` | inpatient index + 30d flag |
| `gold.fact_survey_response` | scored PRO administration |
| `gold.mart_patient_360` | patient rollup |
| `gold.mart_utilization` | age×sex×setting (k-suppressed) |
| `gold.mart_prom_trajectory` | PRO change from baseline |
| `gold.mart_clinical_survey_linkage` | clinical ∪ PRO spine |

## Metrics

Versioned SQL in `conf/metrics/semantic_metrics.sql`.

## Run

```bash
make build-gold
```
