# Platform Assumptions

Defensible defaults chosen for a regulated healthcare research setting.
Template placeholders from the mission brief are resolved here.

| Placeholder | Chosen value | Rationale |
|---|---|---|
| `{{ORG}}` | **Indominus Health Research Consortium** (`INDHC`) | Matches project naming; used in catalogs, tags, and cost attribution. |
| `{{SYNTHETIC_SOURCE}}` | **Synthea** (FHIR R4 + CSV export) | Industry-standard open synthetic patient generator; no real PHI. |
| `{{STORAGE}}` | `stindominushclake` | ADLS Gen2 account name pattern; hierarchical namespace enabled. |
| `{{AZURE_REGION}}` | `eastus2` | Strong Azure Databricks / Private Link coverage; single-region metastore. |
| `{{UC_METASTORE}}` | `uc_metastore_eastus2` | One Unity Catalog metastore per region. |
| `{{CATALOGS}}` | `hc_dev`, `hc_test`, `hc_prod` | Strict environment isolation; prod data never flows backward. |
| `{{SURVEY_INSTRUMENTS}}` | PHQ-9, GAD-7, PROMIS-29, EQ-5D-5L, SF-36 | Common PRO suite covering depression, anxiety, multi-domain HRQoL. |
| `{{DEID_STANDARD}}` | **HIPAA Safe Harbor** (45 CFR §164.514(b)(2)) | Deterministic, auditable; Expert Determination reserved for future LDS expansions. |
| `{{SMALL_CELL_K}}` | **11** | Common research disclosure threshold (CMS-style); configurable in `conf/`. |
| `{{RETENTION_YEARS}}` | **7** | Aligns with typical HIPAA documentation retention; study-specific holds may extend. |

## Technical assumptions (Phase 0+)

1. **Local demo runtime**: PySpark + `delta-spark` on a developer machine; Databricks Connect is optional and degrades gracefully when unavailable.
2. **Ingestion default**: Databricks Auto Loader (`cloudFiles`); Azure Data Factory documented as the alternative for on-prem/SFTP.
3. **Python**: 3.10–3.12 preferred for Spark compatibility; 3.13 supported for non-Spark tooling where possible.
3a. **JDK**: Local PySpark requires **JDK 11 or 17** (`JAVA_HOME`). JDK 21+ fails with Hadoop `Subject.getSubject` errors.
3b. **Windows**: Local Spark requires `winutils.exe`; run `python scripts/setup_windows_hadoop.py` (also part of `make setup`).
4. **De-identification salt**: Loaded from Databricks secret scope / Key Vault in cloud; local mode uses a deterministic demo salt from env (`HC_DEID_SALT`) that must never be used in production.
5. **Compliance posture**: This repository implements *technical safeguards that support* HIPAA Privacy and Security Rule expectations. Organizational policy, BAAs, training, and audit remain outside the code and are required for compliance.
6. **Synthetic-only in git**: Checked-in samples and fixtures contain only synthetic identifiers shaped to fail PHI scanners (e.g. clearly fake tokens), never real MRN/SSN/NPI patterns.

## Change control

Assumptions that affect architecture or privacy must be recorded as ADRs under `docs/adr/` and updated here in the same PR.
