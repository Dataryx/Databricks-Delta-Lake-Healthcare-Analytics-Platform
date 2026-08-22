# Synthetic data generator

## Purpose

Produce a **deterministic, synthetic-only** clinical + patient-reported outcome (PRO)
corpus for local demos and tests. No real PHI is generated or committed.

## Source

| Label | Meaning |
|-------|---------|
| `synthea_sim` | Python simulator of Synthea FHIR R4 / CSV entity shapes |
| `survey_sim` | Longitudinal PRO simulator (PHQ-9, GAD-7, PROMIS-29, EQ-5D-5L, SF-36) |

Full Synthea JAR execution is optional later; this simulator guarantees offline
reproducibility without Java Synthea dependencies.

## Seed

Default seed: **42** (`conf/platform.yml` → `synthetic.seed`).

```bash
python scripts/generate_synthetic.py --seed 42 --patients 100 --output data/synthetic
# or
make generate-synthetic
```

## Outputs

```
data/synthetic/
  landing/clinical/*.csv   # full corpus (gitignored)
  landing/survey/*.csv
  landing/MANIFEST.json
  sample/*.csv             # tiny subset committed for review
```

## Survey design

- Waves: baseline, 30/90/180/365-day
- Missingness: wave skip (~8%), partial completion (~12%), dropout after random wave
- Quality flags: straight-lining (~4%), out-of-window (~5%)
- Every score row carries `scoring_version` for reproducibility

## Identifiers

All IDs use `SYN-*` tokens. Do not introduce MRN/SSN/NPI/email/phone/ZIP+4 shaped
literals — the PHI scanner will fail the build.
