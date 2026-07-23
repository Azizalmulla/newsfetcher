# Phase 9 evidence pack

**Recommendation: green (local cascade; external logo API gated on cost approval)**

## Delivered

- Migration `0012_phase9_logos`
  - `tenant_logo_templates` (variants, track_role own/competitor/other, thresholds)
  - `logo_detections` (bbox, confidence, stage, evidence)
  - `logo_matches` (proposed-only by default)
  - `report_items.logo_match_id`
- Cost-controlled cascade: local screen → fingerprint similarity → optional external stub
- APIs under `/api/v1/logos/*`
  - template upload
  - detect → propose
  - human decision (only path to `included`)
- Report draft pulls included logo matches
- Celery queue `logo.detect`
- Eval fixture `tests/fixtures/logo_eval.json`
- Threat register T13 / T14
- Health phase `9`

## Invariants

- Detector never sets match status to `included`
- External provider requires pinned model + key; still pre-screens locally
- No claim of perfect logo recall

## Tests

```text
apps/api logo + full suite green
```
