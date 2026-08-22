# ADR 0003: Local batch Bronze ingest with Auto Loader parity

- **Status:** Accepted
- **Date:** 2026-08-21

## Context

Production ingestion uses Databricks Auto Loader (`cloudFiles`) with schema
evolution, rescued data, and per-source checkpoints. Local demo machines cannot
run `cloudFiles`.

## Decision

1. Implement shared Bronze transforms (`add_technical_columns`, hash-based
   idempotency, CDF on write) used by both paths.
2. Default local path: batch CSV → Delta append with hash anti-join.
3. `try_autoloader_stream` attempts `cloudFiles` and logs a clear degrade message
   when unavailable (never crash the demo).

## Consequences

- `make demo` / `scripts/ingest_bronze.py` work offline.
- Cloud wiring in DLT/Workflows (Phase 10) reuses the same technical-column contract.
