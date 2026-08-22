# Assumptions

These are the defaults we chose for INDHC so the repo can run without a long
questionnaire. If you change something that affects privacy or architecture,
update this file and add or amend an ADR under `docs/adr/`.

## Organization and platform

| Topic | Choice | Why |
|-------|--------|-----|
| Organization | Indominus Health Research Consortium (`INDHC`) | Matches naming used in catalogs and cost tags |
| Synthetic source | Synthea-compatible Python generator | Open shapes, no real PHI |
| Azure region | `eastus2` | Solid Databricks / Private Link coverage |
| Storage account | `stindominushclake` | ADLS Gen2 with hierarchical namespace |
| Unity Catalog metastore | `uc_metastore_eastus2` | One metastore per region |
| Catalogs | `hc_dev`, `hc_test`, `hc_prod` | Hard env split; no prod → dev flow |
| Survey instruments | PHQ-9, GAD-7, PROMIS-29, EQ-5D-5L, SF-36 | Common PRO coverage |
| De-identification | HIPAA Safe Harbor | Deterministic and auditable |
| Small-cell threshold | 11 | Common research disclosure practice; set in `config/` |
| Retention | 7 years | Typical documentation retention; studies may hold longer |

## Engineering

1. Local demo uses PySpark + delta-spark. Databricks Connect is optional.
2. Cloud ingest prefers Auto Loader; ADF is the documented fallback for SFTP/on-prem.
3. Python 3.10–3.12 is the sweet spot for Spark. Use JDK 11 or 17 locally — not 21+.
4. On Windows, run `python scripts/setup_windows_hadoop.py` (also part of `make setup`).
5. The de-id pepper comes from Key Vault / secret scope in cloud. Local mode uses
   `HC_DEID_SALT` from `.env`, which must never be reused in production.
6. Git only holds synthetic identifiers shaped to fail the PHI scanner.

## ML and ops

7. Appointment no-show labels in the local demo are synthetic (~20%). They exist to
   exercise the training path, not to reflect real attendance.
8. Medication adherence in features is an order-density proxy, not true PDC.
9. Models are research artifacts, not clinical devices.
10. Local MLflow tracks under `artifacts/mlflow`. Unity Catalog registration is tagged
    for cloud apply.
11. Cloud Bronze → Silver uses DLT; local keeps the batch scripts with the same package.
12. Prod deploys need GitHub Environment approval plus workspace secrets.
13. Terraform stands up storage and Key Vault by default; live UC resources are opt-in.
