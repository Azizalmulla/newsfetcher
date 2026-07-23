# ADR 0003 — Source ingestion priority

## Status

Accepted (Phase 0)

## Context

Mandatory Kuwaiti sources vary in legal/technical accessibility. Blind scraping creates legal and reliability risk.

## Decision

Preferred connector order:

1. Licensed / official API
2. RSS / Atom
3. XML sitemap
4. Public structured endpoint
5. Static HTML fetch
6. Playwright browser rendering
7. Public e-paper download where legally permitted

No connector may bypass paywalls, auth walls, or bot protections. Every source remains in the registry even when ingestion is disabled. KUNA Arabic and English are separate channels under one publisher.

## Consequences

Phase 0 registers sources only. Live connectors begin in Phase 1 after documented assessments and legal gates.
