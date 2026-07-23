# ADR 0004 — Object storage for binaries

## Status

Accepted (Phase 0)

## Context

The platform will store PDFs, page renders, OCR artifacts, cuttings, logos, previews, and immutable final reports.

## Decision

- Store all large binaries in S3-compatible object storage
- Keep PostgreSQL for metadata, hashes, provenance, and pointers
- Use MinIO for local development
- Serve downloads via signed URLs

## Consequences

No large document blobs in Postgres. Retention and takedown workflows operate on object keys plus metadata rows.
