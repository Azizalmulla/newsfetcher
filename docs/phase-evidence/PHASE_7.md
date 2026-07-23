# Phase 7 evidence pack

**Recommendation: green (conditional on pinning `MISTRAL_OCR_MODEL` before production OCR)**

## Delivered

- Migration `0010_phase7_epaper`
  - `epaper_editions` / `epaper_pages`
  - `ocr_blocks` (bbox + provenance)
  - `cuttings` (proposed → review)
  - `report_items.cutting_id` report integration
- Seed: Al-Anbaa `epaper_ar` channel (connector disabled, legal gate pending)
- PDF ingest with SHA-256 + object storage
- Text-layer extraction via `pypdf`
- OCR resolver: text layer → Mistral (when key+model pinned) → local stub fallback
- Keyword matching → proposed cuttings with evidence
- Review adjust (status/note/bbox)
- Report draft includes included cuttings
- APIs under `/api/v1/epaper/*`
- Celery route: `cutting.generate`
- Health phase `7`

## Gates preserved

- Live/licensed ingest requires `legal_gate=approved` + enabled `epaper` connector
- Ungated fixture upload restricted to `platform_admin` (`allow_ungated_fixture=true`)
- No automatic legal approval

## Tests

```text
apps/api: 31 passed
ruff + mypy: pass
```

## Production note

```env
OCR_PROVIDER=mistral
MISTRAL_API_KEY=...
MISTRAL_OCR_MODEL=<pin from official Mistral OCR 4 docs>
```
