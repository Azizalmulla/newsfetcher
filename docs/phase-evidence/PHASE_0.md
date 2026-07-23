# Phase 0 evidence pack

**Status recommendation: green (conditional on first git commit + remote CI once pushed)**

**Freeze:** Do not start Phase 1 without explicit authorization.

## Artifact / build identifier

- Phase: `0`
- Local verification date: `2026-07-22`
- Commit hash: _pending first commit_ (repository initialized; changes staged locally)

## Exact scope delivered

- Monorepo scaffold (`apps/api`, `apps/web`, `packages/*`, `infra/*`, `docs/*`)
- Docker Compose: Postgres+pgvector (host port **5433**), Redis, MinIO, API, worker
- FastAPI health/ready + source inventory read API
- Celery worker heartbeat on `source.health` (no live ingestion)
- Alembic migrations `0001`–`0004`
- Idempotent seed: 10 publishers, 11 channels (KUNA AR+EN), all `pending_assessment`
- ADRs, threat/risk register, source assessment template
- CI workflow (GitHub Actions)
- Next.js Phase 0 shell (Next 16.2.11)
- Env schema with OCR/embedding model IDs configurable (not hardcoded)

## Database migrations

| Revision | Purpose |
|----------|---------|
| `0001_extensions` | `pgcrypto`, `vector` |
| `0002_tenancy_skeleton` | `tenants`, `roles`, `permissions`, `role_permissions` |
| `0003_source_registry` | publishers/channels/assessments/connectors/fetch runs/failures |
| `0004_observability_jobs` | `job_runs`, `audit_logs` |

Downgrade path: `uv run alembic downgrade base`

## Tests added

- `apps/api/tests/test_seed_inventory.py`
- `apps/api/tests/test_config.py`
- `apps/api/tests/test_health.py`
- `apps/api/tests/test_no_live_scrape.py`
- `apps/api/tests/test_db_seed_integration.py`

## Test results (local)

```text
uv run ruff check .     -> All checks passed
uv run mypy app         -> Success: no issues found in 24 source files
uv run pytest -q        -> 11 passed
```

## Runtime smoke (Compose)

```text
GET /health -> {"status":"ok","service":"newsfetcher","phase":"0"}
GET /ready  -> {"status":"ok","database":"ok","redis":"ok"}
GET /api/v1/sources/inventory -> publisher_count=10 channel_count=11 pending_assessment_count=11
KUNA channels languages = {ar, en}
```

Services verified up: `postgres`, `redis`, `minio`, `api`, `worker`.

## Security checks

- `.env` gitignored; only `.env.example` tracked
- No provider keys in frontend
- Secret redaction helper present
- No Playwright / live scraper modules in Phase 0
- Connector configs seeded with `enabled=false`
- Compose Postgres mapped to **5433** to avoid colliding with host Postgres on 5432

## Manual verification steps

1. `cp .env.example .env`
2. `make bootstrap`
3. `make up` (or data-plane + API as documented)
4. Open http://localhost:8000/health
5. Open http://localhost:8000/api/v1/sources/inventory
6. Confirm all assessments are `pending_assessment` and no connector is enabled
7. `make test`

## Remaining risks

- Remote CI not yet executed (no remote push)
- Web Compose service not required for Phase 0 API gate; local `pnpm build` succeeded
- Host Postgres on 5432 can confuse local tooling if `DATABASE_URL` still points at 5432
- LLM/email/cloud/auth decisions deferred
- Source legal assessments still entirely pending

## Rollback instructions

1. Stop stack: `docker compose -f infra/compose/docker-compose.yml down -v`
2. Drop schema if needed: `uv run alembic downgrade base`
3. Discard Phase 0 code: `git reset --hard` / remove repo if no commit yet
4. No production deploy occurred

## Recommendation

**green** for Phase 0 local baseline.

Awaiting explicit authorization before Phase 1 (source assessment + connector framework).
