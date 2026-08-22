# Cohorts and reproducibility

## Cohorts

Declarative YAML under `conf/cohorts/`. Compiler materializes `gold.cohort_<name>`
and registers provenance in `ops.cohort_registry`.

```bash
make build-cohort COHORT=inpatient_utilizers
# or
python scripts/build_cohort.py --name t2dm_phq9
```

Each cohort row carries `definition_hash`, IRB id, and creating principal.

## Manifests

`ops.run_manifest` plus sidecar `artifacts/<artifact>/RESEARCH_MANIFEST.json` with:

- input table Delta versions
- git commit SHA
- definition hash
- output checksum
- runtime version / principal

## Reproduce

```bash
python -m hc_lakehouse.reproducibility.reproduce \
  --manifest artifacts/cohort_inpatient_utilizers/RESEARCH_MANIFEST.json
```

Exit 0 only when re-derived key checksum matches the manifest (fail closed).
