# NewsFetcher

Kuwait-focused media intelligence and digital press-clipping SaaS.

**Current freeze point: Phase 0 — repository and architecture baseline.**

No live newspaper scraping is enabled in this phase.

## Stack

- FastAPI + SQLAlchemy 2 + Alembic + Celery
- PostgreSQL + pgvector
- Redis
- MinIO (S3-compatible)
- Next.js + TypeScript

## Quick start

Prerequisites: Docker, Docker Compose, [uv](https://github.com/astral-sh/uv), Node 22+, pnpm 9+.

```bash
cp .env.example .env
make bootstrap
make up
```

The API container runs migrations and seeds the mandatory source registry on startup.

- API health: http://localhost:8000/health
- Source inventory: http://localhost:8000/api/v1/sources/inventory
- Web shell: http://localhost:3000
- MinIO console: http://localhost:9001

## Local API tests (without full Compose web build)

```bash
# start only data plane
docker compose -f infra/compose/docker-compose.yml up -d postgres redis minio minio-init
make migrate
make seed
make test
```

> Local note: Compose Postgres is published on host port **5433** (not 5432) to avoid clashes with a system Postgres install.


## Phase gate

Phase 0 is complete only when migrations, seed invariants, CI, and docs are green — and **no** live source connectors have been activated.

Do not start Phase 1 without explicit authorization.

## Docs

- [Architecture overview](docs/architecture/overview.md)
- [ADRs](docs/adr/)
- [Risk register](docs/risks/threat-risk-register.md)
- [Source assessment template](docs/sources/SOURCE_ASSESSMENT_TEMPLATE.yaml)
