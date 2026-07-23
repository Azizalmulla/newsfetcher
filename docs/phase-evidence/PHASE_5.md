# Phase 5 evidence pack

**Recommendation: green (conditional on verifying Voyage model IDs against the live account before production)**

## Delivered

- Migration `0008_phase5_semantic`
  - `article_embeddings` / `entity_embeddings` (pgvector)
  - `semantic_candidates`
  - `relevance_decisions`
  - `tenant_match_thresholds`
- Embedding providers: Voyage (when `VOYAGE_API_KEY` set) + local deterministic fallback
- Rerank providers: Voyage + local overlap fallback
- Pipeline: retrieve → rerank → lexical evidence aggregate → rules classifier → review
- Explainable provenance on every semantic candidate
- APIs:
  - `POST /api/v1/semantic/run`
  - `GET /api/v1/semantic/candidates`
  - `POST /api/v1/semantic/candidates/{id}/decision`
  - `GET/PUT /api/v1/semantic/thresholds`
- Celery routes: `matching.semantic`, `matching.rerank`
- Semantic never auto-finalizes; human review required

## Tests

```text
apps/api: 27 passed
ruff + mypy: pass
```

## Production note

Set and verify:

```env
VOYAGE_API_KEY=...
EMBEDDING_MODEL=voyage-4-large
RERANK_MODEL=rerank-2.5
EMBEDDING_DIMENSIONS=<confirm against Voyage response>
EMBEDDING_FALLBACK_LOCAL=false
```

Local fallback is for tests/dev only.
