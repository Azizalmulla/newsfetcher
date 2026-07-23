# Phase 8 evidence pack

**Recommendation: green**

## Goal

Close every mandatory source channel into one formal disposition without live scraping:

| Disposition | Meaning in Phase 8 |
|-------------|--------------------|
| `active` | Connector implemented + configured; **still** `legal_gate=pending`, `enabled=false` |
| `awaiting_licensing` | Needs license / public-edition confirmation |
| `temporarily_broken` | Known failure + recovery plan |
| `blocked` | Formal legal/access block (none applied yet) |

## Delivered

- Migration `0011_phase8_source_closure`
  - `source_assessments.phase8_disposition`
  - `recovery_plan` JSONB
  - `closure_notes`
- Closure matrix: `docs/sources/PHASE8_SOURCE_CLOSURE_MATRIX.yaml` (12/12 channels)
- Assessment YAML for `alanba__epaper_ar`
- Connector registry expansions: `browser`, `licensed_api`, `epaper` (inert discover)
- HTML/sitemap connector configs per channel in matrix
- Seed applies Phase 8 closure after registry seed
- APIs: `GET /api/v1/sources/closure`, `POST /api/v1/sources/closure/apply`
- E-paper channels skip homepage HTML probes in `run_assessments`
- Health phase `8`

## Closure snapshot (matrix)

- **active (9):** alanba/alqabas/alrai/alwasat/arabtimes/kuwaittimes web + aljarida/alseyassah/alwatan html
- **awaiting_licensing (1):** alanba/epaper_ar
- **temporarily_broken (2):** kuna web_ar + web_en (RSS/transport; HTML recovery plan)
- **blocked (0)**

## Gates preserved

- Apply path forces `connector.enabled=False`
- Legal gate stays `pending` (never set to `approved` by closure/assessment code)
- Stub connectors return zero discovery items

## Tests

```text
apps/api: phase8 + guardrail tests green with full suite
packages/connectors: epaper/browser/licensed_api registered
```
