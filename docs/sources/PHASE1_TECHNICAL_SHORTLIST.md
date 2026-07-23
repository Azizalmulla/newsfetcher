# Phase 1 technical shortlist

Technical probes completed for all 11 channels. **Legal gate remains `pending` for every source.** No connector is enabled for live ingestion.

## Recommended first cohort (technical only)

| Rank | Publisher | Channel | Connector | Why |
|------|-----------|---------|-----------|-----|
| 1 | Al-Anbaa | web_ar | sitemap | robots allow + sitemap inventory |
| 2 | Al Qabas | web_ar | sitemap | robots allow + sitemap |
| 3 | Al Rai | web_ar | sitemap | robots allow + sitemap |
| 4 | Al Wasat | web_ar | sitemap | robots allow + sitemap |

Alternates with sitemap: Arab Times (en), Kuwait Times (en).

## Full technical outcomes

| Publisher/Channel | Status | Connector | RSS | Sitemap | Robots |
|-------------------|--------|-----------|-----|---------|--------|
| alanba/web_ar | approved_for_html_fetch | sitemap | no | yes | yes |
| alqabas/web_ar | approved_for_html_fetch | sitemap | no | yes | yes |
| alrai/web_ar | approved_for_html_fetch | sitemap | no | yes | yes |
| alwasat/web_ar | approved_for_html_fetch | sitemap | no | yes | yes |
| arabtimes/web_en | approved_for_html_fetch | sitemap | no | yes | yes |
| kuwaittimes/web_en | approved_for_html_fetch | sitemap | no | yes | yes |
| aljarida/web_ar | approved_for_html_fetch | html | no | no | yes |
| alseyassah/web_ar | approved_for_html_fetch | html | no | no | unknown |
| alwatan/web_ar | approved_for_html_fetch | html | no | no | yes |
| kuna/web_ar | approved_for_html_fetch | html | no | no | unknown |
| kuna/web_en | approved_for_html_fetch | html | no | no | unknown |

Notes:

- Common `/rss` paths often returned HTML; feeds are accepted only after `feedparser` validation.
- KUNA required urllib fallback due to malformed `Transfer-Encoding` headers.
- Per-channel YAML assessments: `docs/sources/assessments/`.

## Gate before Phase 3 live fetch

1. Legal review sets `legal_gate=approved` per channel.
2. Set `SourceConnectorConfig.enabled=true` only after that.
3. Prefer shortlist sitemap connectors first.
