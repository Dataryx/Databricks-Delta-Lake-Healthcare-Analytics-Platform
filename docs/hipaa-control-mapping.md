# HIPAA technical control mapping (supportive — not a certification)

> This repository implements **technical safeguards that support** HIPAA Privacy and
> Security Rule expectations. Organizational policies, BAAs, workforce training, and
> independent audit remain required. **This is not a HIPAA certification.**

| Safeguard theme | Example regulatory concepts | Repository control |
|---|---|---|
| Minimum necessary | Privacy Rule access limitation | Group-only Unity Catalog grants from `conf/governance/access_matrix.yml`; deny defaults; no `account users` grants |
| De-identification | Safe Harbor §164.514(b)(2) | HMAC `patient_sk`, ZIP3, age bands; methodology in `docs/deidentification-methodology.md` |
| Access control | §164.312(a) | SCIM groups, schema isolation (`restricted`, `sandbox`), break-glass re-id log |
| Audit controls | §164.312(b) | `ops.access_audit_daily`, `ops.reid_request_log`, `ops.pipeline_run_log` |
| Integrity | §164.312(c) | Delta CDF, DQ fail-closed gate, quarantine path (no silent drops) |
| Transmission / secrets | §164.312(e) | Key Vault / secret scope for de-id pepper; no secrets in git (`.env.example` only) |
| Retention | Organizational policy | Configurable `retention_years` (default 7) on audit rows |
| Disclosure limitation | Small-cell / aggregate | `k=11` suppression on utilization mart and dashboard SQL `HAVING COUNT(*) >= 11` |
| Contingency | Admin safeguards (aligned) | DR runbook with RPO/RTO; Delta time travel |
| Workforce / training | Admin safeguards | Researcher onboarding notebook + governance docs (org still owns training) |

## Explicit non-claims

- No claim of HIPAA “compliance” or certification as a fact.
- Synthetic data only in this repository; production PHI handling requires org controls beyond code.
- ML models are research / decision-support artifacts, not clinical devices.
