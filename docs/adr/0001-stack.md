# ADR 0001 — Core stack

## Status

Accepted (Phase 0)

## Context

The product requires Arabic NLP, OCR, PDF manipulation, embeddings, multi-tenant SaaS APIs, and a bilingual dashboard.

## Decision

- Backend: Python, FastAPI, Pydantic, SQLAlchemy 2, Alembic, Celery, Redis
- Database: PostgreSQL + pgvector
- Frontend: Next.js, TypeScript, React
- Object storage: S3-compatible (MinIO locally)
- Package tooling: `uv` (Python), `pnpm` (Node)

## Consequences

Python remains the system of record for ingestion, matching, OCR orchestration, and report generation. The Next.js app is the tenant UX surface and must not hold provider secrets.
