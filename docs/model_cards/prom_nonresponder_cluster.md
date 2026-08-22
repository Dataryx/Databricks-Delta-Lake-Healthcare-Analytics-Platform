# Model card: prom_nonresponder_cluster

- **Version:** 1.0.0
- **Generated:** 2026-08-22T22:16:47.233493+00:00

## Critical disclaimer

Models are research and decision-support artifacts only. They are not medical devices, diagnostic tools, or clinical advice.

## Intended use

Exploratory clustering of synthetic PRO scores to surface non-responder-like patterns for research hypothesis generation.

## Features

`EQ-5D-5L`, `GAD-7`, `PHQ-9`, `PROMIS-29`, `SF-36`

## Overall metrics

```json
{'n_patients': 85, 'n_clusters': 3, 'nonresponder_cluster': 2}
```

## Fairness / subgroup performance

| slice | value | n | accuracy | auc |
|---|---|---:|---:|---:|

## Training notes

KMeans k=3 on standardized instrument means. Models are research and decision-support artifacts only. They are not medical devices, diagnostic tools, or clinical advice.

## Out of scope

- Not for diagnosis, triage, or autonomous clinical decision-making.
- Not validated as a medical device.
