# ADR 0005 — Observability baseline

## Status

Accepted (Phase 0)

## Context

Every ingestion and processing stage must be traceable.

## Decision

- Structured JSON logs by default
- Sentry optional via `SENTRY_DSN`
- OpenTelemetry optional via OTLP endpoint
- `job_runs` and `source_fetch_runs` / `source_failures` tables for operational history
- Queue names reserved up front for stage-level routing

## Consequences

Missing DSN/endpoint disables exporters without failing startup. Later phases must write job-run rows for each stage.
