# Architecture overview (Phase 0)

```text
Next.js web ──▶ FastAPI API ──▶ PostgreSQL (+ pgvector)
                    │                ▲
                    ├──────────▶ Redis / Celery queues
                    └──────────▶ MinIO (S3)
```

## Processes

| Process | Role in Phase 0 |
|---------|-----------------|
| `api` | Health, readiness, source inventory read API |
| `worker` | Celery heartbeat on `source.health` only |
| `web` | Brand shell + API health display |
| `postgres` | Schema + source registry |
| `redis` | Broker/backend |
| `minio` | Local object storage bucket |

## Non-goals for Phase 0

- Live HTTP fetching of newspaper sites
- Authentication / tenant CRUD
- Matching, OCR, embeddings, report PDF generation
