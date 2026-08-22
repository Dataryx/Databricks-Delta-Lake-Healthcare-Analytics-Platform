# Model card: appointment_noshow

- **Version:** 1.0.0
- **Generated:** 2026-08-22T21:17:21.719810+00:00

## Critical disclaimer

Models are research and decision-support artifacts only. They are not medical devices, diagnostic tools, or clinical advice.

## Intended use

Research prediction of synthetic ambulatory appointment no-show labels. Labels are simulated for pipeline demonstration only.

## Features

`sex`, `race`, `ethnicity`, `age_band`, `care_setting_key`, `encounters_90d`, `inpatient_90d`, `ed_90d`, `avg_los_90d`, `score_value`

## Overall metrics

```json
{'n': 59, 'positive_rate': 0.2711864406779661, 'accuracy': 0.7288135593220338, 'auc': 0.5443313953488371, 'brier': 0.20387907983375647}
```

## Fairness / subgroup performance

| slice | value | n | accuracy | auc |
|---|---|---:|---:|---:|
| age_band | 0 | 1 | 1.0 | None |
| age_band | 1 | 13 | 0.7692307692307693 | 0.3666666666666666 |
| age_band | 2 | 1 | 0.0 | None |
| age_band | 3 | 7 | 0.42857142857142855 | 0.08333333333333334 |
| age_band | 4 | 16 | 0.75 | 0.6770833333333333 |
| age_band | 5 | 3 | 0.3333333333333333 | 0.25 |
| age_band | 6 | 8 | 1.0 | None |
| age_band | 7 | 10 | 0.8 | 0.15625 |
| sex | 0 | 6 | 0.6666666666666666 | 0.5625 |
| sex | 1 | 8 | 0.75 | 0.5 |
| sex | 2 | 30 | 0.8 | 0.48958333333333337 |
| sex | 3 | 15 | 0.6 | 0.5648148148148149 |
| race | 0 | 11 | 0.6363636363636364 | 0.6785714285714286 |
| race | 1 | 10 | 1.0 | None |
| race | 2 | 7 | 0.2857142857142857 | 0.8 |
| race | 3 | 15 | 0.8 | 0.4583333333333333 |
| race | 4 | 16 | 0.75 | 0.5416666666666666 |
| ethnicity | 0 | 23 | 0.7391304347826086 | 0.42156862745098034 |
| ethnicity | 1 | 18 | 0.7222222222222222 | 0.6692307692307693 |
| ethnicity | 2 | 18 | 0.7222222222222222 | 0.7230769230769231 |
| payer_group | SYN-PAYER-A | 36 | 0.6944444444444444 | 0.46545454545454545 |
| payer_group | SYN-PAYER-B | 9 | 1.0 | None |
| payer_group | SYN-PAYER-C | 14 | 0.6428571428571429 | 0.5222222222222223 |

## Training notes

Patient-level split; sigmoid-calibrated HGB. Models are research and decision-support artifacts only. They are not medical devices, diagnostic tools, or clinical advice.

## Out of scope

- Not for diagnosis, triage, or autonomous clinical decision-making.
- Not validated as a medical device.
