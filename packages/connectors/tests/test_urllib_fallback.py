from __future__ import annotations

from newsfetcher_connectors.politeness import PoliteHttpClient


def test_urllib_fallback_fetches_kuna_homepage() -> None:
    client = PoliteHttpClient(
        user_agent="NewsFetcherBot/0.1 (+test)",
        politeness_delay_ms=0,
        max_requests_per_minute=60,
        transport_fallback="urllib",
        timeout_seconds=25.0,
    )
    try:
        response = client.get("https://www.kuna.net.kw/", use_cache=False)
        assert response.status_code == 200
        assert len(response.content) > 1000
        assert b"html" in response.content[:200].lower()
    finally:
        client.close()
