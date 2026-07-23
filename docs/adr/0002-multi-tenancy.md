# ADR 0002 — Multi-tenancy model

## Status

Accepted (Phase 0 skeleton; auth in Phase 2)

## Context

Strict tenant isolation is mandatory for a SaaS press-clipping product.

## Decision

- Shared-database, shared-schema tenancy with a required `tenant_id` on tenant-owned rows
- Backend-enforced tenant scoping on every tenant query
- Platform-owned tables (publishers, source channels, assessments) have no tenant_id
- Initial roles: Platform Admin, Tenant Admin, Editor/Reviewer, Viewer
- Automated cross-tenant isolation tests required from Phase 2

## Consequences

Frontend filtering alone is never sufficient. Row-level checks and integration tests are part of the definition of done for tenant features.
