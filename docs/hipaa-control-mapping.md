# HIPAA technical controls in this repo

These are the technical safeguards we built to support HIPAA Privacy and Security
Rule expectations. They do not replace BAAs, policies, workforce training, or an
independent audit. This document is not a certification.

| Theme | What we mean in practice | Where it shows up |
|-------|--------------------------|-------------------|
| Minimum necessary | Only approved groups get table access | `config/governance/access_matrix.yml` |
| De-identification | Safe Harbor style tokens and geo/age generalization | `docs/deidentification-methodology.md` |
| Access control | SCIM groups, restricted schemas, break-glass log | governance package + ops tables |
| Audit | Who queried what, re-id requests, pipeline runs | `ops.*` tables |
| Integrity | Fail-closed DQ, quarantine, Delta change feed | quality package + Silver/Gold builds |
| Secrets | Pepper and keys stay out of git | Key Vault / secret scope; `.env.example` only |
| Retention | Configurable audit retention (default 7 years) | platform config |
| Small cells | Suppress thin aggregates | k=11 on marts and dashboard SQL |
| Contingency | Restore from Delta history / DR runbook | `docs/runbooks/` |
| Training support | Onboarding notebook and docs | org still owns formal training |

## What we are not claiming

- HIPAA "compliance" or certification as a fact
- That synthetic demo data equals a production PHI environment
- That ML models are clinical devices or medical advice
