# Silver layer (Phase 3)

Conformed, validated clinical entities with fail-closed quarantine.

## Delivered in Phase 3

- YAML schema contracts under `conf/contracts/` with StructType loader
- Cleansing: trim, null-token normalization, casing, timestamp parse, dedupe
- Referential integrity for encounter→patient and lab→patient/encounter
- Quarantine tables under `.local_delta/quarantine/` with reason codes
- Core tables: `silver.patient`, `silver.encounter`, `silver.lab_result`
- Direct identifier columns (names, full ZIP, DOB string) excluded from Silver

## Deferred to Phase 4 (privacy)

- HMAC-SHA256 crosswalk (`restricted.*`)
- Deterministic date shift / Safe Harbor / LDS variant
- Full SCD2 MERGE for demographics

## Run

```bash
make ingest-bronze
make build-silver
```
