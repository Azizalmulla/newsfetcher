# Phase 4 evidence pack

**Recommendation: green**

## Delivered

- Migration `0007_phase4_matching` (`text_matches`, `match_evidence`)
- Deterministic layered matcher:
  1. exact
  2. case-insensitive English
  3. Arabic-normalized
  4. alias
  5. controlled fuzzy (≥0.92, min length 6)
- Exclusion phrases veto matches
- Every match stores explainable evidence spans (no unexplained AI matches)
- Tenant match inbox API:
  - `GET /api/v1/matches/inbox`
  - `POST /api/v1/matches/{id}/decision` (include/exclude)
  - `POST /api/v1/matches/run`
- Celery route `matching.lexical`
- Arabic/English fixture corpus under `tests/fixtures/matching_corpus.json`

## Tests

```text
apps/api: 21 passed
packages/connectors: 4 passed
ruff + mypy: pass
```

## Explicitly deferred

- Semantic embeddings / Voyage / rerank (Phase 5)
- Live source ingestion still gated by legal approval (Phase 3 gate unchanged)
