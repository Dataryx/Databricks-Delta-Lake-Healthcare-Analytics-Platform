# Machine learning (research artifacts)

> **Disclaimer:** Models are research and decision-support artifacts only. They are
> **not** medical devices, diagnostic tools, or clinical advice.

## Feature tables (`ml` schema)

Point-in-time keyed by `patient_key` + `feature_as_of`:

| Table | Grain |
|-------|-------|
| `ml.ft_patient_demographics` | patient |
| `ml.ft_utilization_90d` | patient × as-of (90d look-back, no look-ahead) |
| `ml.ft_lab_trends` | patient × as-of (180d) |
| `ml.ft_prom_scores` | patient × instrument |
| `ml.ft_comorbidity_index` | patient (Charlson-like proxy) |
| `ml.ft_medication_adherence` | patient (order-density proxy, not true PDC) |

```bash
make build-features
```

## Models

Configured in [`conf/ml/models.yml`](../conf/ml/models.yml).

| Model | Purpose |
|-------|---------|
| `readmission_30d` | Calibrated HGB on inpatient 30-day readmission |
| `appointment_noshow` | Calibrated HGB on synthetic ambulatory no-show labels |
| `prom_nonresponder_cluster` | KMeans on PRO instrument means |
| Propensity utility | 1:1 NN matching on propensity scores |

Guardrails:

- Train/test split by **patient**, never by row
- Temporal holdout helper for as-of features
- Fairness slices: age_band, sex, race, ethnicity, payer_group
- Model cards under `docs/model_cards/`
- MLflow tracking at `artifacts/mlruns`; UC name tagged as `{catalog}.ml.{model}`

```bash
make train-ml
```

## ADR

See [ADR 0009](adr/0009-ml-research-guardrails.md).
