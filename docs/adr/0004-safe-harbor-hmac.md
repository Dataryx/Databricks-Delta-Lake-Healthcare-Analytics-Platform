# ADR 0004: HIPAA Safe Harbor with HMAC crosswalk

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Silver must stop PHI. Options: Safe Harbor vs Expert Determination.

## Decision

1. Implement **HIPAA Safe Harbor** (45 CFR §164.514(b)(2)) transforms in code.
2. Surrogate keys = **HMAC-SHA256** of source ids with environment pepper from Key Vault
   (`HC_DEID_SALT` locally).
3. Crosswalk lives only in ``restricted.patient_xref``.
4. ZIP → ZIP3 with low-population nulling; ages >89 → ``90+``; names/MRN-like tokens stripped.
5. Deterministic per-patient date offset (±365 days) available for event dates (Phase 4 helper).

## Consequences

- Auditable, deterministic de-id suitable for research demos.
- Expert Determination / LDS full-date variant remains a Phase 4+/8 grant pattern.
