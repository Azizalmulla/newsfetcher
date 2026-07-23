# X (Twitter) official API — Phase 10 checklist

Live social polling is **blocked** until every item below is complete.

| Gate | Meaning | Config / DB flag |
|------|---------|------------------|
| Credentials available | Bearer token (or OAuth app) provisioned in secrets | `X_API_BEARER_TOKEN` + `credentials_available` |
| Pricing reviewed | Current usage-based X API pricing verified for the live account | `pricing_reviewed` |
| Endpoints confirmed | Exact user-timeline / search endpoints pinned from official docs | `X_API_BASE_URL`, `endpoints_confirmed` |
| Terms documented | Display/storage/redistribution terms recorded | this file + `terms_documented` |
| Cost approved | Client explicitly approves expected spend | `cost_approved` |
| Live enabled | Ops flip after all of the above | `live_enabled` + `X_API_LIVE_ENABLED=true` |

## Hard rules

- Do **not** scrape `x.com` / `twitter.com` HTML or unofficial APIs.
- Track only **approved official outlet accounts** initially.
- Fixture ingest is allowed for tests without live credentials.
- Matches are always `proposed` until human review.

## Initial outlet shortlist (handles only — not live-fetched)

| Handle | Outlet |
|--------|--------|
| `@KUNAonline` | KUNA |
| `@alanba_news` | Al-Anbaa |
| `@alqabas` | Al Qabas |
| `@KuwaitTimes` | Kuwait Times |

Update handles if official accounts change; keep `is_approved=false` until ops review.
