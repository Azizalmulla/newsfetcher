# Phase 10 evidence pack

**Recommendation: green (live X polling remains gated off)**

## Delivered

- Migration `0013_phase10_social`
  - `social_integration_gates`
  - `social_accounts` / `social_posts` / `social_matches`
  - `report_items.social_match_id`
- Official X client (`GatedXApiClient`) — refuses calls unless checklist + secrets complete
- Fixture ingest path for tests (not a scrape)
- Outlet handle shortlist seeded (`is_approved=false` by default)
- Checklist doc: `docs/sources/SOCIAL_X_TERMS_COST_CHECKLIST.md`
- APIs under `/api/v1/social/*`
- Celery queue `social.poll`
- Report draft includes human-included social matches
- Health phase `10`

## Gates (all required for live)

credentials · pricing_reviewed · endpoints_confirmed · terms_documented · cost_approved · live_enabled · `X_API_LIVE_ENABLED` · bearer token

## Hard rules preserved

- No HTML scrape of x.com / twitter.com
- No Playwright / unofficial APIs
- Matches stay `proposed` until review

## Tests

```text
apps/api: social pipeline + no-scrape guards green with full suite
```
