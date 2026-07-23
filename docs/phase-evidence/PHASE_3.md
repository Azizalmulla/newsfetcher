# Phase 3 evidence pack

**Recommendation: green (ingestion gated; no live newspaper fetch enabled)**

## Delivered

- Migration `0006_phase3_articles` (articles, versions, images, story clusters)
- Canonical URL normalization + title fingerprint clustering
- Discovery service with hard gates:
  - `legal_gate == approved`
  - `connector.enabled == true`
- API: `POST /api/v1/ingestion/discover/{publisher}/{channel}`
- Celery task routed to `source.discovery`
- Gate tests proving pending legal blocks discovery

## Tests

```text
apps/api: 19 passed
packages/connectors: 4 passed
```

## Current production posture

- All 11 channels assessed technically
- Technical shortlist ready (Al-Anbaa, Al Qabas, Al Rai, Al Wasat)
- **0 connectors enabled**
- **0 legal gates approved**
- Live discovery attempts fail closed with `legal_gate_pending`

## Unblock for live shortlist ingestion

For each shortlisted channel:

1. Complete legal review → set `source_assessments.legal_gate = approved`
2. Set `source_connector_configs.enabled = true`
3. Confirm sitemap/feed URLs in connector config
4. Run discovery via API or Celery
