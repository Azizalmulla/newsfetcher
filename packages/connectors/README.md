# newsfetcher-connectors

Phase 1 connector framework:

- `SourceConnector` interface
- `RssConnector`, `SitemapConnector`, `HtmlConnector`
- Polite HTTP client (rate limit, retry backoff, conditional requests, circuit breaker)
- Passive assessment probes (`robots.txt`, RSS, sitemap)

Connectors discover URLs only. Enabling live ingestion requires:

1. Technical assessment status
2. `legal_gate=approved`
3. `SourceConnectorConfig.enabled=true`
