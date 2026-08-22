# ADR 0008: Access matrix as code with local SQL artifacts

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Unity Catalog grants must be reviewable in PRs and fail closed for PHI-adjacent assets.

## Decision

1. Encode group × asset × privilege × justification in YAML.
2. CI renders SQL and a grants-diff; humans approve.
3. Local/demo writes SQL + ops metadata tables; does not invent live UC grants.
4. Break-glass re-id requires `ops.reid_request_log` before crosswalk use.

## Consequences

- Reviewable least-privilege changes.
- Cloud apply wired in Phase 10 Asset Bundle / CD.
