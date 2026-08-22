# Model card: readmission_30d

- **Version:** 1.0.0
- **Generated:** 2026-08-22T21:17:06.907999+00:00

## Critical disclaimer

Models are research and decision-support artifacts only. They are not medical devices, diagnostic tools, or clinical advice.

## Intended use

Research risk stratification for 30-day all-cause readmission among synthetic inpatient index stays. Not for clinical use.

## Features

`sex`, `race`, `ethnicity`, `age_band`, `encounters_90d`, `inpatient_90d`, `ed_90d`, `avg_los_90d`, `lab_count_180d`, `distinct_labs_180d`, `mean_lab_value_180d`, `charlson_proxy`, `distinct_conditions`

## Overall metrics

```json
{'n': 31, 'positive_rate': 0.03225806451612903, 'accuracy': 0.967741935483871, 'auc': 0.8500000000000001, 'brier': 0.02949269368624207}
```

## Fairness / subgroup performance

| slice | value | n | accuracy | auc |
|---|---|---:|---:|---:|
| age_band | 0 | 1 | 1.0 | None |
| age_band | 1 | 6 | 0.8333333333333334 | 0.7 |
| age_band | 2 | 4 | 1.0 | None |
| age_band | 3 | 1 | 1.0 | None |
| age_band | 5 | 6 | 1.0 | None |
| age_band | 6 | 8 | 1.0 | None |
| age_band | 7 | 5 | 1.0 | None |
| sex | 0 | 6 | 1.0 | None |
| sex | 1 | 8 | 1.0 | None |
| sex | 2 | 8 | 0.875 | 0.7142857142857143 |
| sex | 3 | 9 | 1.0 | None |
| race | 0 | 6 | 1.0 | None |
| race | 1 | 10 | 0.9 | 0.5555555555555556 |
| race | 2 | 2 | 1.0 | None |
| race | 3 | 11 | 1.0 | None |
| race | 4 | 2 | 1.0 | None |
| ethnicity | 0 | 12 | 0.9166666666666666 | 0.8181818181818181 |
| ethnicity | 1 | 10 | 1.0 | None |
| ethnicity | 2 | 9 | 1.0 | None |
| payer_group | SYN-PAYER-A | 9 | 0.8888888888888888 | 0.6875 |
| payer_group | SYN-PAYER-B | 8 | 1.0 | None |
| payer_group | SYN-PAYER-C | 14 | 1.0 | None |

## Training notes

Patient-level split; calibrated HistGradientBoosting (isotonic). Models are research and decision-support artifacts only. They are not medical devices, diagnostic tools, or clinical advice.

## Out of scope

- Not for diagnosis, triage, or autonomous clinical decision-making.
- Not validated as a medical device.
