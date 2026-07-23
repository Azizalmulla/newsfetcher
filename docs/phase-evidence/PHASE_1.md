# Phase 1 evidence pack

**Recommendation: green (conditional on legal approval before any live ingestion)**

## Delivered

- Connector package `packages/connectors` with RSS / sitemap / HTML connectors
- Polite HTTP client: delay, RPM limit, retries, conditional cache headers, circuit breaker
- Assessment probe + persistence + YAML docs for all 11 channels
- Source health dashboard API: `GET /api/v1/sources/health`
- Assessment API: `POST /api/v1/sources/assess`
- Fixture tests for connectors
- Technical shortlist of 4 sources (legal still pending; connectors disabled)

## Tests

```text
packages/connectors: 4 passed
apps/api: 12 passed
ruff + mypy: pass
```

## Security / legal controls

- No Playwright
- No paywall bypass helpers
- `legal_gate` forced to `pending` by assessment writer
- `connector.enabled=false` for all channels after assessment
- Live article fetch not activated

## Rollback

- Disable assessment endpoints / revert connector package dependency
- `alembic` schema unchanged from Phase 0 (no new migrations required for Phase 1)
- Assessment rows can be reset to `pending_assessment` via re-seed notes or SQL
