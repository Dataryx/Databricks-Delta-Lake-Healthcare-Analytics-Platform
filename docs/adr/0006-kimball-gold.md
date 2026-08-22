# ADR 0006: Kimball gold over Data Vault

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Mission requires analysis-ready models for researchers on day one.

## Decision

Use **Kimball star schemas** (conformed dimensions + facts) plus purpose-built
research marts. Defer Data Vault hubs/links/satellites — higher modeling cost
without payoff for this research Lakehouse's query patterns.

## Consequences

- Clear grain documentation and surrogate keys in Gold.
- Silver remains the conformed enterprise layer; Gold is consumption-oriented.
- Vault can be revisited if multi-source audit genealogy becomes primary.
