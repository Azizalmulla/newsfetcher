# Phase 8 source closure summary

Authoritative machine matrix: [`PHASE8_SOURCE_CLOSURE_MATRIX.yaml`](./PHASE8_SOURCE_CLOSURE_MATRIX.yaml).

Apply via:

```bash
curl -X POST http://localhost:8000/api/v1/sources/closure/apply \
  -H "Authorization: Bearer $TOKEN"
```

Or seed (applies automatically after publisher/channel registry).

## Before live fetch

1. Legal sets `legal_gate=approved` per channel (manual / future admin tool with dual confirm).
2. Ops sets `SourceConnectorConfig.enabled=true` only after that.
3. Prefer sitemap shortlist first; promote KUNA from `temporarily_broken` only after recovery probes pass.
4. E-paper remains `awaiting_licensing` until license terms are recorded.
