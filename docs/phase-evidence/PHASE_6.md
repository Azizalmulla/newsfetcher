# Phase 6 evidence pack

**Recommendation: green**

## Delivered

- Migration `0009_phase6_reports`
  - `tenant_branding`
  - `reports` / `report_items`
  - `report_versions` (immutable snapshot + PDF pointers + delivery state)
- Object storage helper (`local` for tests/dev, `s3` in Compose)
- PDF renderer (`reportlab`) with tenant branding colors/footer
- Email delivery backends: `file` (default), `console`, `smtp`
- Report workflow APIs:
  - draft from included matches
  - review meta / notes / include-exclude
  - reorder
  - approve → immutable version + PDF
  - archive
  - revise (new draft from final/archived)
  - PDF download
  - email deliver
  - branding get/put
- Celery routes: `report.render`, `report.deliver`
- Minimal Next.js review screen at `/reports`
- Health phase `6`

## Tests

```text
apps/api: 29 passed
ruff + mypy: pass
```

## Notes

- Final/archived reports reject mutations (HTTP 409); use `/revise`.
- Compose sets `STORAGE_BACKEND=s3` against MinIO.
- Live SMTP requires `EMAIL_BACKEND=smtp` + SMTP credentials.
